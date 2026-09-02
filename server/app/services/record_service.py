"""通关记录业务逻辑（E1/E2：区域维度 + Redis 缓存）"""

import json
import logging

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.record import Record
from app.core.redis import redis_client
from redis.exceptions import RedisError

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

RANK_CACHE_PREFIX = "rank:best:"
RANK_CACHE_TTL = settings.LEADERBOARD_CACHE_TTL_SECONDS


async def submit_record(user_id: int, level_id: int, clear_time: float, db: AsyncSession) -> Record:
    """提交通关记录"""
    record = Record(user_id=user_id, level_id=level_id, clear_time=clear_time)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    # 新成绩入榜后失效相关排行榜缓存（全国 + 该用户所在区域）
    await _invalidate_rank_cache(level_id)
    return record


async def get_records(user_id: int, db: AsyncSession) -> list[Record]:
    """获取用户的所有通关记录"""
    stmt = select(Record).where(Record.user_id == user_id).order_by(Record.created_at.desc())
    result = await db.execute(stmt)
    records = result.scalars().all()
    return records


def _best_subquery(level_id: int):
    """子查询：每个用户在该关卡的最快成绩"""
    return (
        select(
            Record.user_id,
            sa_func.min(Record.clear_time).label("best_time"),
        )
        .where(Record.level_id == level_id)
        .group_by(Record.user_id)
        .subquery()
    )


async def get_rank(
    db: AsyncSession,
    level_id: int,
    limit: int = 50,
    region: str = "",
    self_user_id: int | None = None,
) -> dict:
    """排行榜：每人取最快成绩（全国 / 指定 region），带 Redis 缓存

    - region 空 = 全国榜；非空 = 该 region_code 榜（按 hd_users.region_code）
    - self_user_id 提供时额外计算我的名次（my_rank，无成绩为 None）
    - Redis 不可用时降级直查（仅告警，不阻断）
    """
    cache_key = f"{RANK_CACHE_PREFIX}{level_id}:{region or 'all'}:{min(limit, 100)}"
    cached = await _get_cached(cache_key)
    if cached is not None:
        rows = cached
    else:
        rows = await _query_rank(db, level_id, limit, region)
        await _set_cached(cache_key, rows)

    result = list(rows)

    # 我的名次（不缓存：随请求用户变化；数量级小，直查可接受）
    my_rank = None
    if self_user_id is not None:
        my_rank = await _query_my_rank(db, level_id, region, self_user_id)

    return {"rank": result, "my_rank": my_rank}


async def _query_rank(db: AsyncSession, level_id: int, limit: int, region: str) -> list[dict]:
    sub = _best_subquery(level_id)

    stmt = (
        select(
            User.id,
            User.nickname,
            User.avatar_url,
            User.region_code,
            sub.c.best_time,
        )
        .join(sub, User.id == sub.c.user_id)
        .order_by(sub.c.best_time.asc(), User.id.asc())
        .limit(limit)
    )
    if region:
        stmt = stmt.where(User.region_code == region)

    rows = (await db.execute(stmt)).all()

    return [
        {
            "rank": idx + 1,
            "user_id": row.id,
            "nickname": row.nickname or f"玩家{row.id}",
            "avatar_url": row.avatar_url or "",
            "region_code": row.region_code or "",
            "best_time": row.best_time,
        }
        for idx, row in enumerate(rows)
    ]


async def _query_my_rank(db: AsyncSession, level_id: int, region: str, user_id: int) -> int | None:
    """我的名次 = 比我的最快成绩更快的人数 + 1（同成绩并列同一位次）"""
    sub = _best_subquery(level_id)

    mine_stmt = (
        select(sub.c.best_time)
        .join(User, User.id == sub.c.user_id)
        .where(sub.c.user_id == user_id)
    )
    if region:
        mine_stmt = mine_stmt.where(User.region_code == region)
    mine = (await db.execute(mine_stmt)).scalar_one_or_none()
    if mine is None:
        return None

    faster_stmt = (
        select(sa_func.count(sa_func.distinct(sub.c.user_id)))
        .join(User, User.id == sub.c.user_id)
        .where(sub.c.best_time < mine)
    )
    if region:
        faster_stmt = faster_stmt.where(User.region_code == region)
    faster = (await db.execute(faster_stmt)).scalar_one()
    return int(faster) + 1


async def _get_cached(key: str) -> list[dict] | None:
    try:
        raw = await redis_client.get(key)
    except RedisError as e:
        logger.warning(f"Redis 读排行榜缓存失败（降级直查）: {e}")
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def _set_cached(key: str, rows: list[dict]) -> None:
    try:
        await redis_client.set(key, json.dumps(rows, ensure_ascii=False), ex=RANK_CACHE_TTL)
    except RedisError as e:
        logger.warning(f"Redis 写排行榜缓存失败（忽略）: {e}")


async def _invalidate_rank_cache(level_id: int) -> None:
    """提交新成绩后失效该关卡的全国榜缓存（区域榜由 TTL 自然过期）"""
    key = f"{RANK_CACHE_PREFIX}{level_id}:all:*"
    try:
        keys = await redis_client.keys(key)
        if keys:
            await redis_client.delete(*keys)
    except RedisError as e:
        logger.warning(f"Redis 失效排行榜缓存失败（忽略）: {e}")
