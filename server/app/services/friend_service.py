"""好友关系业务（E3：邀请码互关 + 好友榜）

- 邀请码：6 位无歧义码表随机串（去 0/O/1/I），懒生成、冲突重试
- 互关：bind 成功 = 双向各插一行；删除好友 = 双向清理
- 好友榜：互关用户在该关卡的最快成绩（口径与全国/区域榜一致），Redis 短缓存
"""

import json
import logging
import secrets

from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy import and_, or_, select, func as sa_func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.relation import UserRelation
from app.models.record import Record
from app.core.redis import redis_client

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 邀请码字符表（去除易混淆 0/O/1/I）
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 6
MAX_FRIENDS = 200  # 单用户好友上限（防滥用）

FRIEND_RANK_CACHE_PREFIX = "friend:rank:"
FRIEND_RANK_CACHE_TTL = settings.LEADERBOARD_CACHE_TTL_SECONDS


def _gen_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


async def ensure_invite_code(db: AsyncSession, user_id: int) -> str:
    """获取/生成我的邀请码（懒生成，写入用户行后返回）"""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not user.invite_code:
        for _ in range(5):  # 撞唯一索引则重试
            code = _gen_code()
            dup = (
                await db.execute(select(User).where(User.invite_code == code))
            ).scalar_one_or_none()
            if dup is None:
                user.invite_code = code
                await db.commit()
                break
        else:
            raise HTTPException(status_code=500, detail="邀请码生成失败，请重试")
    return user.invite_code


async def _friend_ids_query(user_id: int):
    """互关用户 ID 子查询（双向：我关注的人 + 关注我的人）"""
    out = select(UserRelation.user_id).where(UserRelation.friend_id == user_id)
    inc = select(UserRelation.friend_id).where(UserRelation.user_id == user_id)
    return out.union(inc).subquery()


async def _count_friends(db: AsyncSession, user_id: int) -> int:
    sub = await _friend_ids_query(user_id)
    return int((await db.execute(select(sa_func.count()).select_from(sub))).scalar_one())


async def list_friends(db: AsyncSession, user_id: int) -> list[dict]:
    """我的好友列表（按结为好友时间倒序）"""
    rel_rows = (
        await db.execute(
            select(UserRelation)
            .where(or_(
                UserRelation.user_id == user_id,
                UserRelation.friend_id == user_id,
            ))
            .order_by(UserRelation.created_at.desc(), UserRelation.id.desc())
        )
    ).scalars().all()

    friend_ids: list[int] = []
    since_by_id: dict[int, str] = {}
    for rel in rel_rows:
        fid = rel.friend_id if rel.user_id == user_id else rel.user_id
        if fid not in since_by_id:
            since_by_id[fid] = rel.created_at.isoformat() if rel.created_at else None
            friend_ids.append(fid)
    if not friend_ids:
        return []

    users = (
        await db.execute(select(User).where(User.id.in_(friend_ids)))
    ).scalars().all()
    by_id = {u.id: u for u in users}
    return [
        _friend_brief(by_id[fid], since_by_id.get(fid))
        for fid in friend_ids
        if fid in by_id
    ]


def _friend_brief(user: User, created_at: str | None = None) -> dict:
    return {
        "user_id": user.id,
        "nickname": user.nickname or f"玩家{user.id}",
        "avatar_url": user.avatar_url or "",
        "region_code": user.region_code or "",
        "since": created_at,
    }


async def bind_by_code(db: AsyncSession, user_id: int, code: str) -> dict:
    """输入他人邀请码 → 双向互关（幂等：已是好友返回 already）

    - 防自绑：code 属于自己时报错
    - 双方好友数都受 MAX_FRIENDS 上限约束
    """
    code = code.strip().upper()
    if not code or len(code) > 16:
        raise HTTPException(status_code=400, detail="邀请码格式不正确")

    owner = (
        await db.execute(select(User).where(User.invite_code == code))
    ).scalar_one_or_none()
    if owner is None:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    if owner.id == user_id:
        raise HTTPException(status_code=400, detail="不能绑定自己的邀请码")

    # 已是好友 → 幂等返回
    exist = (
        await db.execute(
            select(UserRelation).where(
                UserRelation.user_id == user_id,
                UserRelation.friend_id == owner.id,
            )
        )
    ).scalar_one_or_none()
    if exist is not None:
        return {"matched": True, "friend": _friend_brief(owner)}

    for uid in (user_id, owner.id):
        if await _count_friends(db, uid) >= MAX_FRIENDS:
            raise HTTPException(status_code=400, detail="好友数量已达上限")

    # 双向各插一行（同事务）
    db.add_all(
        [
            UserRelation(user_id=user_id, friend_id=owner.id),
            UserRelation(user_id=owner.id, friend_id=user_id),
        ]
    )
    await db.commit()
    await _invalidate_friend_cache(user_id)
    await _invalidate_friend_cache(owner.id)
    logger.info(f"[friend] user_id={user_id} 绑定好友 {owner.id} code={code}")
    return {"matched": True, "friend": _friend_brief(owner)}


async def unfriend(db: AsyncSession, user_id: int, friend_id: int) -> dict:
    """删除好友（双向清理；非好友时幂等返回 False）"""
    result = await db.execute(
        delete(UserRelation).where(
            or_(
                and_(UserRelation.user_id == user_id, UserRelation.friend_id == friend_id),
                and_(UserRelation.friend_id == user_id, UserRelation.user_id == friend_id),
            )
        )
    )
    if result.rowcount == 0:
        return {"removed": False}
    await db.commit()
    await _invalidate_friend_cache(user_id)
    await _invalidate_friend_cache(friend_id)
    return {"removed": True}


async def get_friend_rank(
    db: AsyncSession,
    user_id: int,
    level_id: int,
    limit: int = 50,
) -> dict:
    """好友榜：互关用户（含自己）在该关卡的最快成绩，按时间升序

    形如全国榜的 items + my_rank（榜内名次）；Redis 短缓存，
    加好友/删好友即时失效，成绩变更靠 TTL 自然过期。
    """
    cache_key = f"{FRIEND_RANK_CACHE_PREFIX}{user_id}:{level_id}:{min(limit, 100)}"
    try:
        raw = await redis_client.get(cache_key)
    except RedisError as e:
        logger.warning(f"Redis 读好友榜缓存失败（降级直查）: {e}")
        raw = None

    if raw is not None:
        try:
            payload = json.loads(raw)
            return {"rank": payload.get("rank", []), "my_rank": payload.get("my_rank")}
        except (json.JSONDecodeError, TypeError):
            pass

    sub = await _friend_ids_query(user_id)
    best = (
        select(
            Record.user_id,
            sa_func.min(Record.clear_time).label("best_time"),
        )
        .where(Record.level_id == level_id)
        .group_by(Record.user_id)
        .subquery()
    )
    stmt = (
        select(User, best.c.best_time)
        .join(best, User.id == best.c.user_id)
        .join(sub, User.id == sub.c.user_id)
        .order_by(best.c.best_time.asc(), User.id.asc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    rank_items = []
    my_idx = None
    for idx, (u, best_time) in enumerate(rows, start=1):
        if u.id == user_id:
            my_idx = idx
        rank_items.append(
            {
                "rank": idx,
                "user_id": u.id,
                "nickname": u.nickname or f"玩家{u.id}",
                "avatar_url": u.avatar_url or "",
                "region_code": u.region_code or "",
                "best_time": best_time,
            }
        )

    payload = {"rank": rank_items, "my_rank": my_idx}
    try:
        await redis_client.set(cache_key, json.dumps(payload, ensure_ascii=False), ex=FRIEND_RANK_CACHE_TTL)
    except RedisError as e:
        logger.warning(f"Redis 写好友榜缓存失败（忽略）: {e}")
    return payload


async def _invalidate_friend_cache(user_id: int) -> None:
    prefix = f"{FRIEND_RANK_CACHE_PREFIX}{user_id}:"
    try:
        keys = await redis_client.keys(f"{prefix}*")
        if keys:
            await redis_client.delete(*keys)
    except RedisError as e:
        logger.warning(f"Redis 失效好友榜缓存失败（忽略）: {e}")
