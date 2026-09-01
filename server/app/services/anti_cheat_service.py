"""服务端行为校验：开局会话、结算限频、作弊日志"""

import json
import logging
import time
from uuid import uuid4

from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client
from app.models.cheat_log import CheatLog
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SESSION_KEY_PREFIX = "session:record:"
RATE_LIMIT_KEY_PREFIX = "rl:submit:"


async def start_session(level_id: int) -> str:
    """开局：生成唯一 session_id，将 {start_time, level_id} 存入 Redis（TTL 1 小时）"""
    session_id = uuid4().hex
    payload = json.dumps({"start_time": time.time(), "level_id": level_id})
    key = SESSION_KEY_PREFIX + session_id
    try:
        await redis_client.set(key, payload, ex=settings.SESSION_TTL_SECONDS)
    except RedisError as e:
        logger.error(f"Redis 写入会话失败: {e}")
        raise HTTPException(status_code=503, detail="服务暂时不可用，请稍后重试")
    return session_id


async def get_session(session_id: str) -> dict:
    """读取开局会话；不存在（过期/重放）抛 400"""
    key = SESSION_KEY_PREFIX + session_id
    try:
        raw = await redis_client.get(key)
    except RedisError as e:
        logger.error(f"Redis 读取会话失败: {e}")
        raise HTTPException(status_code=503, detail="服务暂时不可用，请稍后重试")

    if raw is None:
        raise HTTPException(status_code=400, detail="会话不存在或已过期")

    return json.loads(raw)


async def delete_session(session_id: str) -> None:
    """结算完成后删除会话，防止重放"""
    try:
        await redis_client.delete(SESSION_KEY_PREFIX + session_id)
    except RedisError as e:
        logger.error(f"Redis 删除会话失败: {e}")


async def enforce_submit_rate_limit(user_id: int) -> None:
    """限频：同一用户每分钟最多结算 SUBMIT_RATE_LIMIT_PER_MINUTE 次，超出抛 403"""
    key = f"{RATE_LIMIT_KEY_PREFIX}{user_id}"
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 60)
    except RedisError as e:
        logger.error(f"Redis 限频失败: {e}")
        raise HTTPException(status_code=503, detail="服务暂时不可用，请稍后重试")

    if count > settings.SUBMIT_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=403, detail="操作过于频繁，请稍后再试")


async def log_cheat(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    level_id: int,
    reason: str,
    detail: str = "",
) -> None:
    """记录作弊日志（落库 + 应用日志），便于审计与封禁决策"""
    db.add(CheatLog(user_id=user_id, session_id=session_id, level_id=level_id, reason=reason, detail=detail))
    await db.commit()
    logger.warning(
        f"[CHEAT] user_id={user_id} session_id={session_id} level_id={level_id} reason={reason} detail={detail}"
    )
