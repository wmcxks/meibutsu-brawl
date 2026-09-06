"""好友 API（E3：邀请码互关 + 好友榜）

社交路径：我的「招待」面板展示邀请码/链接 → 好友打开链接或输入码 →
bind 成功后双向互关，排行榜面板「友だち」维度即可见互关成绩。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.schemas.friend import FriendBindRequest
from app.services import friend_service, player_service
from app.utils.response import success, error

router = APIRouter(prefix="/api/friends", tags=["好友"])


@router.get("/invite")
async def my_invite(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """我的邀请码（懒生成；前端拼成带 ?invite= 的分享链接）"""
    code = await friend_service.ensure_invite_code(db, user_id)
    return success(data={"code": code})


@router.get("")
async def list_friends(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """我的好友列表"""
    return success(data={"items": await friend_service.list_friends(db, user_id)})


@router.post("/bind")
async def bind_friend(
    req: FriendBindRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """输入邀请码建立互关（幂等；打开分享链接时自动调用）"""
    try:
        await player_service.assert_user_active(db, user_id)
        return success(data=await friend_service.bind_by_code(db, user_id, req.code))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        return error(message=str(e))


@router.delete("/{friend_id}")
async def remove_friend(
    friend_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """解除好友（双向清理）"""
    return success(data=await friend_service.unfriend(db, user_id, friend_id))


@router.get("/rank")
async def friend_rank(
    level_id: int = Query(default=1, description="关卡ID"),
    limit: int = Query(default=50, le=100, description="返回数量"),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """好友榜（互关用户含自己在内，每关最快成绩）"""
    try:
        return success(data=await friend_service.get_friend_rank(db, user_id, level_id, limit))
    except Exception as e:
        return error(message=str(e))
