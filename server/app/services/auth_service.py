"""登录鉴权业务逻辑"""

from datetime import datetime
from uuid import uuid4

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.middleware.auth_middleware import create_token
from app.schemas.auth import LoginProfile
from config import get_settings

# LINE id_token 校验（PyJWKClient 内部缓存 LINE 公钥，无需每次请求 JWKS）
LINE_JWKS_URL = "https://api.line.me/oauth2/v2.1/certs"
LINE_ISSUER = "https://access.line.me"

_jwks_client = jwt.PyJWKClient(LINE_JWKS_URL)


def _verify_line_id_token(id_token: str) -> dict:
    """校验 LINE id_token（RS256 + 公钥验签 + iss/aud/exp），返回完整 payload

    payload 中的 sub 是 LINE 用户唯一标识；name/picture 仅在申请 profile scope
    时返回，用于回填昵称头像。
    """
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

    if not payload.get("sub"):
        raise HTTPException(status_code=400, detail="LINE 登录凭证缺少用户标识")
    return payload


async def _apply_login_profile(db: AsyncSession, user: User, profile: LoginProfile | None) -> None:
    """登录画像落库：登录计数 / 最近登录时间 / 平台 / 版本 / 地区（A1）"""
    user.last_login_at = datetime.utcnow()
    user.login_count = (user.login_count or 0) + 1
    if profile:
        if profile.platform and not user.platform:
            user.platform = profile.platform  # 注册平台首次写死后不覆盖（绑定场景）
        if profile.client_ver:
            user.client_ver = profile.client_ver
        if profile.country_code:
            user.country_code = profile.country_code
        if profile.region_code:
            user.region_code = profile.region_code
    await db.commit()


async def _get_or_create_user(db: AsyncSession, openid: str) -> User:
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
    return user


async def guest_register(db: AsyncSession) -> dict:
    """临时游客注册：每次调用创建全新游客用户（旧版，仅作过渡，勿在前端使用）"""
    user = await _get_or_create_user(db, f"guest-{uuid4().hex}")

    token = create_token(user.id)
    return {
        "token": token,
        "user_id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
    }


async def guest_login(guest_uuid: str, db: AsyncSession, profile: LoginProfile | None = None) -> dict:
    """H5 游客静默登录：按 guest_uuid 查找用户，不存在则创建，再签发 token

    guest_uuid 复用在 openid 字段（加 guest: 前缀命名空间）。
    """
    openid = f"guest:{guest_uuid}"
    user = await _get_or_create_user(db, openid)
    await _apply_login_profile(db, user, profile)

    token = create_token(user.id)
    return {
        "token": token,
        "user_id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
    }


async def line_login(id_token: str, db: AsyncSession, profile: LoginProfile | None = None) -> dict:
    """LINE LIFF 登录：校验 id_token → 按 LINE 用户标识查找/创建用户 → 签发统一 JWT

    LINE 用户唯一标识（sub）存储在 openid 字段（line: 前缀命名空间）。
    """
    # 1. 校验 LINE id_token（验签 + iss/aud/exp），失败抛 400/503
    claims = _verify_line_id_token(id_token)

    # 2. 按 line:sub 查找或创建用户
    openid = f"line:{claims['sub']}"
    user = await _get_or_create_user(db, openid)

    # 3. profile scope 下回填 LINE 昵称/头像（仅在为空时）
    if claims.get("name") and not user.nickname:
        user.nickname = claims["name"]
    if claims.get("picture") and not user.avatar_url:
        user.avatar_url = claims["picture"]

    await _apply_login_profile(db, user, profile)

    # 4. 签发 token，响应结构与游客登录一致
    token = create_token(user.id)
    return {
        "token": token,
        "user_id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
    }
