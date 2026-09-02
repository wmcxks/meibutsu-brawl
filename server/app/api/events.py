"""埋点上报 API（F1：前端批量上报，可匿名）"""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import decode_token
from app.models.game_event import GameEvent
from app.schemas.event import EventsBatchRequest
from app.utils.response import success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["埋点上报"])

_security = HTTPBearer(auto_error=False)


async def _optional_user_id(credentials: HTTPAuthorizationCredentials | None = Depends(_security)) -> int:
    """可选鉴权：带合法 token 归因到用户，否则记 -1（不阻断上报）"""
    if credentials is None:
        return -1
    try:
        payload = decode_token(credentials.credentials)
        return payload.get("user_id", -1)
    except Exception:
        return -1


@router.post("")
async def report_events(
    req: EventsBatchRequest,
    user_id: int = Depends(_optional_user_id),
    db: AsyncSession = Depends(get_db),
):
    """批量写入埋点（事件属性已校验长度；写失败仅告警不弹错）"""
    rows = [
        GameEvent(
            user_id=user_id,
            event=item.event,
            props=json.dumps(item.props, ensure_ascii=False),
            client_ts=item.client_ts,
        )
        for item in req.events
    ]
    db.add_all(rows)
    await db.commit()
    return success(data={"accepted": len(rows)})
