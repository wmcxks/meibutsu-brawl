"""登录鉴权 API 路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import GuestLoginRequest, LineLoginRequest
from app.services import auth_service
from app.utils.response import success, error

router = APIRouter(prefix="/api/auth", tags=["登录鉴权"])


@router.post("/guest")
async def guest_register(db: AsyncSession = Depends(get_db)):
    """临时游客注册（旧版，仅作过渡）"""
    try:
        data = await auth_service.guest_register(db)
        return success(data=data)
    except Exception as e:
        return error(message=str(e))


@router.post("/guest-login")
async def guest_login(req: GuestLoginRequest, db: AsyncSession = Depends(get_db)):
    """H5 游客静默登录（guest_uuid 换 token）"""
    try:
        data = await auth_service.guest_login(req.guest_uuid, db)
        return success(data=data)
    except Exception as e:
        return error(message=str(e))


@router.post("/line")
async def line_login(req: LineLoginRequest, db: AsyncSession = Depends(get_db)):
    """LINE LIFF 登录（id_token 换统一 JWT）"""
    try:
        data = await auth_service.line_login(req.id_token, db)
        return success(data=data)
    except HTTPException:
        # 凭证无效/服务不可用等语义错误保持原 HTTP 状态码透传
        raise
    except Exception as e:
        return error(message=str(e))
