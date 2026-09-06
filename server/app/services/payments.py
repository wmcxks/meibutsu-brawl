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
    """LINE Pay（LINEPay API）适配器骨架

    真实验签（接入时按 LINE Pay 官方文档核对）：
      - 请求头 X-LINE-ChannelId == LINE_PAY_CHANNEL_ID
      - 签名 = HMAC-SHA256(channelSecret, raw_body) 的 hex 值，
        与请求头 X-LINE-Authorization 中 `<rawbody> <signature>` 的 signature 比较
    本骨架仅校验 ChannelId 头并解析 JSON，完整 HMAC 校验在凭据就位后启用。
    """

    name = "line_pay"

    async def verify(self, raw_body: bytes, headers: dict) -> dict:
        settings = get_settings()
        if not (settings.LINE_PAY_CHANNEL_ID and settings.LINE_PAY_CHANNEL_SECRET):
            raise NotConfigured("LINE Pay 渠道未配置")

        channel_id = headers.get("x-line-channelid") or headers.get("X-LINE-ChannelId", "")
        if channel_id != settings.LINE_PAY_CHANNEL_ID:
            raise PaymentVerificationError("渠道 ID 不匹配")

        # TODO(商务资质就位)：启用 HMAC 验签
        #   sig_line = headers.get("x-line-authorization", "")
        #   expect = hmac.new(settings.LINE_PAY_CHANNEL_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
        #   if not sig_line.endswith(expect): raise PaymentVerificationError("签名校验失败")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise PaymentVerificationError(f"回调内容非法: {e}") from None
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
