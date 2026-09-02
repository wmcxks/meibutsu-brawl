"""订单业务（C3：商品目录 + 下单 + 确认收款发货）

支付渠道接入前：pending 订单由运营后台 mark-paid（代收/测试）；
接入真实渠道后补回调验签，发货路径复用 mark_paid 同一逻辑。
"""

import logging
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.services import wallet_service

logger = logging.getLogger(__name__)

# 商品目录（占位定价；正式定价/文案走后续商品表）
CATALOG: dict[str, dict] = {
    "gem_60":   {"name": "ジェム 60",   "currency": "gem", "amount": 60},
    "gem_330":  {"name": "ジェム 330",  "currency": "gem", "amount": 330},
    "gem_1200": {"name": "ジェム 1200", "currency": "gem", "amount": 1200},
}


def get_products() -> list[dict]:
    return [
        {"sku": sku, "name": meta["name"], "currency": meta["currency"], "amount": meta["amount"]}
        for sku, meta in CATALOG.items()
    ]


async def create_order(db: AsyncSession, user_id: int, sku: str) -> dict:
    """下单：生成 pending 订单（幂等键 order_no）

    规则：同一用户同时只允许一笔 pending 订单（防重复下单/刷单），
    支付完成或取消后方可再下。
    """
    meta = CATALOG.get(sku)
    if meta is None:
        raise HTTPException(status_code=404, detail="商品不存在")

    pending = (
        await db.execute(
            select(Order).where(Order.user_id == user_id, Order.status == "pending")
        )
    ).scalar_one_or_none()
    if pending is not None:
        raise HTTPException(status_code=409, detail="已有待支付订单，请先完成或取消")

    order_no = f"HD{int(time.time())}{uuid4().hex[:12].upper()}"
    order = Order(
        order_no=order_no,
        user_id=user_id,
        sku=sku,
        currency=meta["currency"],
        amount=meta["amount"],
        status="pending",
        channel="manual",
    )
    db.add(order)
    await db.commit()
    logger.info(f"[order] user_id={user_id} create {order_no} sku={sku}")
    return {"order_no": order_no, "sku": sku, "status": order.status}


async def cancel_pending(db: AsyncSession, user_id: int) -> dict:
    """取消当前用户待支付订单（手动取消；后续接渠道后由用户操作页触发）"""
    pending = (
        await db.execute(
            select(Order).where(Order.user_id == user_id, Order.status == "pending")
        )
    ).scalar_one_or_none()
    if pending is None:
        return {"cancelled": False}
    pending.status = "cancelled"
    await db.commit()
    logger.info(f"[order] user_id={user_id} cancel {pending.order_no}")
    return {"cancelled": True, "order_no": pending.order_no}


async def mark_paid(
    db: AsyncSession,
    order_no: str,
    provider_receipt: str = "",
    channel: str = "manual",
) -> dict:
    """确认收款并发货（幂等：已 paid 订单直接返回，不重复发货）

    发货 = 钱包账本 credit（event_id=order_no 唯一，天然幂等）；
    若发货失败，订单保持 paid，走运营补偿补发（有流水可查）。
    """
    stmt = select(Order).where(Order.order_no == order_no)
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status == "paid":
        return {"order_no": order_no, "status": "paid", "already": True}

    # 1) 状态置 paid（先占位，防止并发重复发货）
    order.status = "paid"
    order.channel = channel
    if provider_receipt:
        order.provider_receipt = provider_receipt[:512]
    await db.commit()

    # 2) 发货：钱包账本（event_id 幂等）
    balance = await wallet_service.credit(
        db, order.user_id, order.currency, order.amount,
        event_type="purchase", event_id=f"order:{order_no}", detail=order.sku,
    )

    logger.info(f"[order] {order_no} paid via {channel} -> {order.currency} +{order.amount}")
    return {"order_no": order_no, "status": "paid", "currency": order.currency, "balance": balance}
