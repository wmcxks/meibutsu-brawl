"""任务/签到 API（A7）"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.schemas.mission import MissionClaimRequest
from app.services import mission_service, player_service
from app.utils.response import success

router = APIRouter(prefix="/api/missions", tags=["任务"])


@router.get("")
async def list_missions(
    scope: str = Query(default="daily", description="任务周期：daily / weekly / achievement"),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """任务列表（含我的进度与领取状态）"""
    items = await mission_service.list_missions(db, user_id, scope)
    return success(data={"items": items})


@router.post("/claim")
async def claim_mission(
    req: MissionClaimRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """领取任务奖励"""
    try:
        await player_service.assert_user_active(db, user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    data = await mission_service.claim_mission(db, user_id, req.mission_key, req.period)
    return success(data=data)
