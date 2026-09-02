"""奖励发放 API（C1：所有"+道具"类奖励唯一入口）"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.schemas.reward import RewardGrantRequest
from app.services import player_service, reward_service
from app.utils.response import success

router = APIRouter(prefix="/api/rewards", tags=["奖励发放"])


@router.post("/grant")
async def grant_reward(
    req: RewardGrantRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """道具奖励发放（广告 / 分享 / 运营补偿统一收口）

    防刷：nonce 幂等 + 渠道每日上限 + 道具/数量白名单 + 封禁校验。
    """
    try:
        await player_service.assert_user_active(db, user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    data = await reward_service.grant_prop(db, user_id, req.placement, req.prop_key, req.amount, req.nonce)
    return success(data=data)
