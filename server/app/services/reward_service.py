"""奖励发放业务（C1）

所有「+1 道具」类奖励必须走 /api/rewards/grant 这一个入口，三层防刷：
  1. nonce 幂等（Redis SETNX，7 天内同一 nonce 只生效一次）
  2. 渠道每日上限（Redis INCR，按 placement × 用户 × UTC 日）
  3. 道具键/数量白名单（服务端硬编码，客户端不可传任意值）
Redis 不可用时 fail-closed（503），宁可拒发不可漏防。
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client
from app.models.player_daily import PlayerDaily
from app.models.user_prop import UserProp
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

NONCE_KEY_PREFIX = "reward:nonce:"
CAP_KEY_PREFIX = "reward:cap:"

# 合法道具键（与 hd_user_props / 前端 PropManager 对齐）
VALID_PROP_KEYS = {"move_out", "undo", "shuffle", "peek"}
# 合法渠道（新增渠道在此登记，便于统一归因与风控）
VALID_PLACEMENTS = {"ad:reward", "share:invite", "op:compensation"}


async def _check_nonce(nonce: str) -> None:
    """nonce 幂等：已存在返回冲突，否则占位（TTL 7 天）"""
    try:
        ok = await redis_client.set(
            NONCE_KEY_PREFIX + nonce,
            "1",
            nx=True,
            ex=settings.REWARD_NONCE_TTL_SECONDS,
        )
    except RedisError as e:
        logger.error(f"Redis 写入 nonce 失败: {e}")
        raise HTTPException(status_code=503, detail="服务暂时不可用，请稍后重试") from None
    if not ok:
        raise HTTPException(status_code=400, detail="该奖励已领取，请勿重复请求")


async def _check_daily_cap(user_id: int, placement: str) -> None:
    """渠道每日上限：placement × 用户 × UTC 日"""
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    key = f"{CAP_KEY_PREFIX}{placement}:{user_id}:{day}"
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 86400)
    except RedisError as e:
        logger.error(f"Redis 奖励限频失败: {e}")
        raise HTTPException(status_code=503, detail="服务暂时不可用，请稍后重试") from None
    if count > settings.REWARD_DAILY_CAP_PER_PLACEMENT:
        raise HTTPException(status_code=429, detail="今日该渠道的奖励次数已达上限")


async def _upsert_prop(db: AsyncSession, user_id: int, prop_key: str, amount: int) -> int:
    """道具余额累加（行不存在则建）"""
    stmt = select(UserProp).where(UserProp.user_id == user_id, UserProp.prop_key == prop_key)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = UserProp(user_id=user_id, prop_key=prop_key, balance=amount)
        db.add(row)
    else:
        row.balance = (row.balance or 0) + amount
    await db.commit()
    await db.refresh(row)
    return row.balance


async def _incr_daily_rewards(db: AsyncSession, user_id: int) -> None:
    """当日 rewards 计数 +1（无行则建，与 stats_service 口径一致）"""
    today = datetime.now(timezone.utc).date()
    stmt = select(PlayerDaily).where(PlayerDaily.user_id == user_id, PlayerDaily.stat_date == today)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        db.add(PlayerDaily(user_id=user_id, stat_date=today, rewards=1))
    else:
        row.rewards = (row.rewards or 0) + 1
    await db.commit()


async def grant_prop(db: AsyncSession, user_id: int, placement: str, prop_key: str, amount: int, nonce: str) -> dict:
    """发放道具奖励（C1 唯一入口的执行体）"""
    if placement not in VALID_PLACEMENTS:
        raise HTTPException(status_code=400, detail="未知的奖励渠道")
    if prop_key not in VALID_PROP_KEYS:
        raise HTTPException(status_code=400, detail="未知的道具类型")

    # 1. 幂等 nonce（先占位，Redis 不可用直接 503，不落库）
    await _check_nonce(nonce)

    # 2. 渠道每日上限
    await _check_daily_cap(user_id, placement)

    # 3. 余额累加 + 当日奖励计数
    balance = await _upsert_prop(db, user_id, prop_key, amount)
    await _incr_daily_rewards(db, user_id)

    logger.info(f"[reward] user_id={user_id} placement={placement} prop={prop_key} +{amount} balance={balance}")
    return {"placement": placement, "prop_key": prop_key, "amount": amount, "balance": balance}
