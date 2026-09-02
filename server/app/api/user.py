"""玩家信息 API（资料 / 统计 / 道具钱包余额）"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.services import player_service
from app.utils.response import success, error

router = APIRouter(prefix="/api/user", tags=["玩家信息"])


@router.get("/me")
async def get_me(user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """当前用户资料 + 累计统计 + 道具/钱包余额（登录后前端拉取一次）"""
    try:
        data = await player_service.get_player_summary(db, user_id)
        return success(data=data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return error(message=str(e))
