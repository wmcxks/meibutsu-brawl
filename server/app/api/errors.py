"""客户端错误上报 API（F3：前端崩溃采集入口）

匿名可用（无 token 记 -1）；写失败仅告警不返回错误——错误通道
本身不能成为新的故障点。
"""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import redis_client
from app.middleware.auth_middleware import decode_token
from app.models.client_error import ClientError
from app.schemas.error import ErrorReportRequest
from app.utils.response import success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/errors", tags=["错误上报"])

_security = HTTPBearer(auto_error=False)

# 每用户（含匿名桶）每小时最多上报条数（Redis 限流，可用则用）
RATE_LIMIT_PER_HOUR = 60


async def _optional_user_id(credentials: HTTPAuthorizationCredentials | None = Depends(_security)) -> int:
    if credentials is None:
        return -1
    try:
        payload = decode_token(credentials.credentials)
        return payload.get("user_id", -1)
    except Exception:
        return -1


async def _throttled(key: str) -> bool:
    """简单限流：超限返回 True（Redis 不可用时放行）"""
    rk = f"err:rate:{key}"
    try:
        cur = await redis_client.incr(rk)
        if cur == 1:
            await redis_client.expire(rk, 3600)
        return cur > RATE_LIMIT_PER_HOUR
    except Exception:
        return False


@router.post("")
async def report_error(
    req: ErrorReportRequest,
    user_id: int = Depends(_optional_user_id),
    db: AsyncSession = Depends(get_db),
):
    """落库一条前端错误（限流后仍丢弃但不报错）"""
    if await _throttled(str(user_id)):
        return success(data={"accepted": False, "reason": "rate_limited"})

    row = ClientError(
        user_id=user_id,
        platform=req.platform[:16],
        client_ver=req.client_ver[:32],
        page_url=req.page_url[:512],
        message=req.message[:512],
        stack=req.stack,
        extras=json.dumps(req.extras, ensure_ascii=False) if req.extras else None,
        client_ts=req.client_ts,
    )
    db.add(row)
    try:
        await db.commit()
    except Exception as e:
        logger.error(f"[errors] 落库失败（丢弃，避免拖垮错误通道）: {e}")
        await db.rollback()
    return success(data={"accepted": True})
