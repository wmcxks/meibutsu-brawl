"""登录鉴权业务逻辑"""

from uuid import uuid4

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.middleware.auth_middleware import create_token
from config import get_settings

# LINE id_token 校验（PyJWKClient 内部缓存 LINE 公钥，无需每次请求 JWKS）
LINE_JWKS_URL = "https://api.line.me/oauth2/v2.1/certs"
LINE_ISSUER = "https://access.line.me"

_jwks_client = jwt.PyJWKClient(LINE_JWKS_URL)


def _verify_line_id_token(id_token: str) -> str:
    """校验 LINE id_token（RS256 + 公钥验签 + iss/aud/exp），返回 LINE 用户唯一标识 sub"""
    settings = get_settings()
    if not settings.LINE_CHANNEL_ID:
        raise HTTPException(status_code=500, detail="服务端未配置 LINE_CHANNEL_ID")

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(id_token)
        payload = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.LINE_CHANNEL_ID,
            issuer=LINE_ISSUER,
        )
    except (jwt.PyJWKClientError, jwt.InvalidTokenError):
        # 含签名错误 / 过期 / aud、iss 不匹配等情况
        raise HTTPException(status_code=400, detail="LINE 登录凭证无效") from None
    except Exception:
        # 拉取 LINE 公钥失败等网络异常
        raise HTTPException(status_code=503, detail="LINE 认证服务暂时不可用") from None

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=400, detail="LINE 登录凭证缺少用户标识")
    return sub


async def guest_register(db: AsyncSession) -> dict:
    """临时游客注册：每次调用创建全新游客用户（旧版，仅作过渡，勿在前端使用）"""
    user = User(openid=f"guest-{uuid4().hex}")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 默认昵称，保证排行榜可读
    if not user.nickname:
        user.nickname = f"玩家{user.id}"
        await db.commit()
        await db.refresh(user)

    token = create_token(user.id)

    return {
        "token": token,
        "user_id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
    }


async def guest_login(guest_uuid: str, db: AsyncSession) -> dict:
    """H5 游客静默登录：按 guest_uuid 查找用户，不存在则创建，再签发 token

    guest_uuid 复用在 openid 字段（加 guest: 前缀命名空间，避免与历史遗留数据冲突）。
    """
    openid = f"guest:{guest_uuid}"

    # 1. 按 guest_uuid 查找用户
    stmt = select(User).where(User.openid == openid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # 2. 不存在则创建新游客用户
    if user is None:
        user = User(openid=openid)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # 昵称为空时回填默认值，保证排行榜可读
    if not user.nickname:
        user.nickname = f"玩家{user.id}"
        await db.commit()
        await db.refresh(user)

    # 3. 复用原有 JWT 逻辑签发 token，响应结构不变
    token = create_token(user.id)

    return {
        "token": token,
        "user_id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
    }


async def line_login(id_token: str, db: AsyncSession) -> dict:
    """LINE LIFF 登录：校验 id_token → 按 LINE 用户标识查找/创建用户 → 签发统一 JWT

    LINE 用户唯一标识（sub）存储在 openid 字段（line: 前缀命名空间，
    与 guest: 前缀游客、历史遗留数据天然隔离）。响应结构与游客登录完全一致。
    """
    # 1. 校验 LINE id_token（验签 + iss/aud/exp），失败抛 400/503
    line_sub = _verify_line_id_token(id_token)

    # 2. 按 line:sub 查找或创建用户
    openid = f"line:{line_sub}"
    stmt = select(User).where(User.openid == openid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(openid=openid)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # 昵称为空时回填默认值，保证排行榜可读
    if not user.nickname:
        user.nickname = f"玩家{user.id}"
        await db.commit()
        await db.refresh(user)

    # 3. 复用原有 JWT 逻辑签发 token，响应结构不变
    token = create_token(user.id)

    return {
        "token": token,
        "user_id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
    }
