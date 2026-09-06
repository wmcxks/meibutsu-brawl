"""登录鉴权业务逻辑"""

import logging
from datetime import datetime
from uuid import uuid4

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.record import Record
from app.models.cheat_log import CheatLog
from app.models.player_daily import PlayerDaily
from app.models.wallet import Wallet, WalletLog
from app.models.user_prop import UserProp
from app.models.game_event import GameEvent
from app.models.mission import UserMission
from app.models.relation import UserRelation
from app.models.cosmetic import UserCosmetic
from app.middleware.auth_middleware import create_token
from app.schemas.auth import LoginProfile
from config import get_settings

logger = logging.getLogger(__name__)

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


async def _merge_guest_into_line(db: AsyncSession, line_openid: str, guest_uuid: str) -> int:
    """游客→LINE 绑定（A8）：把本机游客账号数据并入 LINE 账号后删除游客

    - 幂等：游客不存在 / 同一账号时 no-op
    - 冲突合并：道具/钱包按余额相加，每日统计按量相加；
      流水/记录/埋点等无冲突行直接改挂 LINE 用户
    """
    stmt = select(User).where(User.openid == line_openid)
    target = (await db.execute(stmt)).scalar_one_or_none()

    guest_openid = f"guest:{guest_uuid}"
    if guest_openid == line_openid:
        return 0
    guest = (await db.execute(select(User).where(User.openid == guest_openid))).scalar_one_or_none()
    if guest is None:
        return 0
    if target is None:
        # 目标 LINE 用户异常缺失：以游客数据为新账号（防御性）
        guest.openid = line_openid
        guest.platform = "line"
        await db.commit()
        return 0

    gid, tid = guest.id, target.id
    if gid == tid:
        return 0

    # 1) 余额/日统计冲突行：按 key 求和并删除游客行
    for model, merge in (
        (Wallet, {"balance": lambda a, b: a + b}),
        (UserProp, {"balance": lambda a, b: a + b}),
        (PlayerDaily, {"games": lambda a, b: a + b,
                       "wins": lambda a, b: a + b,
                       "play_seconds": lambda a, b: a + b,
                       "ads_watched": lambda a, b: a + b,
                       "rewards": lambda a, b: a + b}),
    ):
        for row in (await db.execute(select(model).where(model.user_id == gid))).scalars().all():
            cols = [c.name for c in model.__table__.primary_key.columns if c.name != "user_id"]
            keys = {c: getattr(row, c) for c in cols}
            tgt = (await db.execute(select(model).where(model.user_id == tid, *[getattr(model, k) == v for k, v in keys.items()]))).scalar_one_or_none()
            if tgt is None:
                row.user_id = tid
                db.add(row)
            else:
                for col, fn in merge.items():
                    setattr(tgt, col, fn(getattr(tgt, col) or 0, getattr(row, col) or 0))
                await db.delete(row)
        await db.commit()

    # 2) 无冲突子表直接改挂
    for model in (Record, WalletLog, GameEvent, CheatLog, UserMission):
        await db.execute(
            model.__table__.update().where(model.user_id == gid).values(user_id=tid)
        )
    await db.commit()

    # 2.1) 好友关系改挂（双向列；目标已有同对关系时丢弃游客那行）
    guest_rels = (
        await db.execute(
            select(UserRelation).where(
                (UserRelation.user_id == gid) | (UserRelation.friend_id == gid)
            )
        )
    ).scalars().all()
    for rel in guest_rels:
        if rel.user_id == gid:
            dup = (
                await db.execute(
                    select(UserRelation).where(
                        UserRelation.user_id == tid, UserRelation.friend_id == rel.friend_id
                    )
                )
            ).scalar_one_or_none()
            rel.user_id = tid if dup is None else None
        else:
            dup = (
                await db.execute(
                    select(UserRelation).where(
                        UserRelation.user_id == rel.user_id, UserRelation.friend_id == tid
                    )
                )
            ).scalar_one_or_none()
            rel.friend_id = tid if dup is None else None
        if rel.user_id is None or rel.friend_id is None:
            await db.delete(rel)
    await db.commit()

    # 2.2) 装扮改挂（同键冲突 = 目标已拥有该装扮，游客行丢弃，保留目标装备态）
    guest_cosmetics = (
        await db.execute(select(UserCosmetic).where(UserCosmetic.user_id == gid))
    ).scalars().all()
    for row in guest_cosmetics:
        dup = await db.get(UserCosmetic, (tid, row.item_key))
        if dup is None:
            row.user_id = tid
        else:
            if row.equipped and not dup.equipped:
                dup.equipped = 1
            await db.delete(row)
    await db.commit()

    # 3) 删除游客账号
    await db.delete(guest)
    await db.commit()
    logger.info(f"[bind] 游客 {gid} 数据已并入 LINE 用户 {tid}")
    return tid


async def line_login(
    id_token: str,
    db: AsyncSession,
    profile: LoginProfile | None = None,
    guest_uuid: str | None = None,
) -> dict:
    """LINE LIFF 登录：校验 id_token → 按 LINE 用户标识查找/创建用户 → 签发统一 JWT

    LINE 用户唯一标识（sub）存储在 openid 字段（line: 前缀命名空间）。
    携带 guest_uuid 时执行游客→LINE 数据并入（A8，防丢号/跨端升级）。
    """
    # 1. 校验 LINE id_token（验签 + iss/aud/exp），失败抛 400/503
    claims = _verify_line_id_token(id_token)

    # 2. 按 line:sub 查找或创建用户
    openid = f"line:{claims['sub']}"
    user = await _get_or_create_user(db, openid)

    # 2.1 游客数据并入（本设备之前以游客身份玩过）
    if guest_uuid:
        try:
            await _merge_guest_into_line(db, openid, guest_uuid)
        except Exception as e:
            # 并入失败不阻断 LINE 登录（数据可下次登录重试）
            logger.warning(f"[bind] 游客并入失败（忽略）: {e}")

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
