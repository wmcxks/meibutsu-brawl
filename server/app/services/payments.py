"""真实支付渠道回调验签骨架（C3）

设计目标：渠道（LINE Pay / LINE 商店 / 其他）回调与 mark-paid 发货解耦——
任何渠道验签通过后只做一件事：解析出「渠道交易号 / 订单号」，
调用 order_service.mark_paid（与后台人工确认同一发货路径）。

当前状态：渠道商务资质未落地，provider 均未启用。
未配置对应凭据时回调返回 501（配置缺失），已配置凭据的渠道走真实验签。

接入新渠道步骤：
1. 在此文件实现 PaymentProvider 子类（verify 完成验签，返回可信交易信息）
2. 在 REGISTRY 注册
3. 凭据写入 server/.env（LINE_PAY_CHANNEL_ID / LINE_PAY_CHANNEL_SECRET）
4. 可选：统一下单时预留给渠道的 reservationId 存到 order.provider_receipt，
   回调按 transactionId 反查订单（见 resolve_order）
"""

import base64
import hashlib
import hmac
import json
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from config import get_settings

logger = logging.getLogger(__name__)


class PaymentVerificationError(Exception):
    """验签失败/回调内容非法"""


class NotConfigured(Exception):
    """渠道凭据未配置，回调无法验签"""


class PaymentProvider:
    """支付渠道适配器基类"""

    name = "base"

    async def verify(self, raw_body: bytes, headers: dict) -> dict:
        """验签并返回可信交易信息 dict（至少含 transaction_id / order_no 之一）"""
        raise NotImplementedError


class LinePayProvider(PaymentProvider):
    """LINE Pay（LINEPay API）适配器

    真实验签（按 LINE Pay 官方约定）：
      - 请求头 X-LINE-ChannelId == LINE_PAY_CHANNEL_ID
      - 请求头 X-LINE-Authorization = "<签名原文> <签名>"，其中：
          签名      = Base64( HMAC-SHA256(key=ChannelSecret, msg=签名原文) )
          回调场景  签名原文 = 我方先前「下单/確認请求」发给 LINE 的原始 body
      - 回调的 HTTP body 不参与签名（可能被渠道转码），一律以 X-LINE-Authorization
        内嵌的原始 body 为准做验签与数据解析
    凭据未配置时抛 NotConfigured（接口层转 501）。
    """

    name = "line_pay"

    async def verify(self, raw_body: bytes, headers: dict) -> dict:
        settings = get_settings()
        if not (settings.LINE_PAY_CHANNEL_ID and settings.LINE_PAY_CHANNEL_SECRET):
            raise NotConfigured("LINE Pay 渠道未配置")

        channel_id = headers.get("x-line-channelid") or headers.get("X-LINE-ChannelId", "")
        if channel_id != settings.LINE_PAY_CHANNEL_ID:
            raise PaymentVerificationError("渠道 ID 不匹配")

        auth = headers.get("x-line-authorization") or headers.get("X-LINE-Authorization", "")
        # 格式："<签名原文> <Base64签名>"（签名原文可能含空格，取最后一个空格分隔）
        split = auth.rsplit(" ", 1)
        if len(split) != 2 or not split[0] or not split[1]:
            raise PaymentVerificationError("缺少签名头")
        signed_body, provided_sig = split[0], split[1]

        expect_sig = base64.b64encode(
            hmac.new(
                settings.LINE_PAY_CHANNEL_SECRET.encode("utf-8"),
                signed_body.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("ascii")
        if not hmac.compare_digest(expect_sig, provided_sig):
            raise PaymentVerificationError("签名校验失败")

        # 回调 HTTP body 不参与签名 → 以签名原文解析业务数据
        try:
            payload = json.loads(signed_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise PaymentVerificationError(f"签名原文不是合法 JSON: {e}") from None
        return {
            "transaction_id": str(payload.get("transactionId") or payload.get("reservationId") or ""),
            "order_no": str(payload.get("order_no") or ""),
            "raw": payload,
        }


REGISTRY: dict[str, PaymentProvider] = {
    LinePayProvider.name: LinePayProvider(),
}


def get_provider(name: str) -> PaymentProvider:
    provider = REGISTRY.get(name)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"未知支付渠道: {name}")
    return provider


async def resolve_order(db: AsyncSession, info: dict) -> Order:
    """回调信息 → 订单（优先业务 order_no，其次按渠道交易号反查）

    渠道交易号是下单后发给渠道 reservationId 的回执，统一下单时应写入
    order.provider_receipt 便于反查。
    """
    order_no = info.get("order_no", "").strip()
    tx_id = info.get("transaction_id", "").strip()

    stmt = None
    if order_no:
        stmt = select(Order).where(Order.order_no == order_no)
    elif tx_id:
        stmt = select(Order).where(Order.provider_receipt == tx_id)
    if stmt is None:
        raise HTTPException(status_code=400, detail="回调缺少订单标识")
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order
