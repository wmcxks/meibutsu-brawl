"""钱包账本业务（C4：所有货币变动唯一通道）

铁律：任何余额变动必须调用 credit/debit，流水（hd_wallet_logs）与余额
同事务写入；event_id 唯一约束保证同一业务事件（订单/任务/补偿）只生效一次。
"""

import logging
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet import Wallet, WalletLog

logger = logging.getLogger(__name__)

VALID_CURRENCIES = {"coin", "gem"}


async def get_balance(db: AsyncSession, user_id: int, currency: str) -> int:
    row = await db.get(Wallet, (user_id, currency))
    return row.balance if row else 0


async def _apply(
    db: AsyncSession,
    user_id: int,
    currency: str,
    delta: int,
    event_type: str,
    event_id: str,
    detail: str = "",
) -> int:
    if currency not in VALID_CURRENCIES:
        raise HTTPException(status_code=400, detail="未知的币种")

    row = await db.get(Wallet, (user_id, currency))
    if row is None:
        if delta < 0:
            raise HTTPException(status_code=400, detail="余额不足")
        row = Wallet(user_id=user_id, currency=currency, balance=0)
        db.add(row)
        await db.flush()

    new_balance = (row.balance or 0) + delta
    if new_balance < 0:
        raise HTTPException(status_code=400, detail="余额不足")
    row.balance = new_balance

    db.add(
        WalletLog(
            user_id=user_id,
            currency=currency,
            delta=delta,
            balance_after=new_balance,
            event_type=event_type,
            event_id=event_id,
            detail=detail,
        )
    )

    try:
        await db.commit()
    except IntegrityError:
        # event_id 重复：该业务事件已入账，静默幂等返回当前余额
        await db.rollback()
        return await get_balance(db, user_id, currency)

    logger.info(f"[wallet] user_id={user_id} {currency} {delta:+d} -> {new_balance} ({event_type}/{event_id})")
    return new_balance


async def credit(
    db: AsyncSession,
    user_id: int,
    currency: str,
    amount: int,
    event_type: str,
    event_id: str,
    detail: str = "",
) -> int:
    """收入（amount > 0）"""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="发放数量必须为正")
    return await _apply(db, user_id, currency, amount, event_type, event_id, detail)


async def debit(
    db: AsyncSession,
    user_id: int,
    currency: str,
    amount: int,
    event_type: str,
    event_id: str,
    detail: str = "",
) -> int:
    """支出（amount > 0，内部转负）"""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="扣除数量必须为正")
    return await _apply(db, user_id, currency, -amount, event_type, event_id, detail)
