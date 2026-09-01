"""通关记录业务逻辑"""

import logging

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)

from app.models.record import Record


async def submit_record(user_id: int, level_id: int, clear_time: float, db: AsyncSession) -> Record:
    """提交通关记录"""
    record = Record(user_id=user_id, level_id=level_id, clear_time=clear_time)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_records(user_id: int, db: AsyncSession) -> list[Record]:
    """获取用户的所有通关记录"""
    stmt = select(Record).where(Record.user_id == user_id).order_by(Record.created_at.desc())
    result = await db.execute(stmt)
    records = result.scalars().all()
    return records


async def get_rank(level_id: int, limit: int, db: AsyncSession) -> list[dict]:
    """获取指定关卡的通关排行榜（每人取最快成绩）"""

    # 子查询：每个用户在该关卡的最快成绩
    sub = (
        select(
            Record.user_id,
            sa_func.min(Record.clear_time).label("best_time"),
        )
        .where(Record.level_id == level_id)
        .group_by(Record.user_id)
        .subquery()
    )

    stmt = (
        select(
            User.id,
            User.nickname,
            User.avatar_url,
            sub.c.best_time,
        )
        .join(sub, User.id == sub.c.user_id)
        .order_by(sub.c.best_time.asc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "rank": idx + 1,
            "user_id": row.id,
            "nickname": row.nickname or f"玩家{row.id}",
            "avatar_url": row.avatar_url or "",
            "best_time": row.best_time,
        }
        for idx, row in enumerate(rows)
    ]
