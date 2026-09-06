"""玩家信息汇总业务（GET /api/user/me）"""

import logging

from sqlalchemy import delete, select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.record import Record
from app.models.cheat_log import CheatLog
from app.models.player_daily import PlayerDaily
from app.models.wallet import Wallet, WalletLog
from app.models.user_prop import UserProp
from app.models.game_event import GameEvent
from app.models.relation import UserRelation
from app.models.order import Order
from app.models.cosmetic import UserCosmetic

logger = logging.getLogger(__name__)

# 已知道具键（返回统一结构，缺省补 0，前端无需判空）
KNOWN_PROP_KEYS = ["move_out", "undo", "shuffle", "peek"]
KNOWN_CURRENCIES = ["coin", "gem"]


async def _load_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise LookupError(f"用户不存在: {user_id}")
    return user


async def assert_user_active(db: AsyncSession, user_id: int) -> None:
    """封禁校验：status=1 的用户拒绝进入游戏/领取奖励（403）"""
    user = await db.get(User, user_id)
    if user is None:
        raise LookupError(f"用户不存在: {user_id}")
    if user.status == 1:
        raise PermissionError("账号已被封禁")


def _user_brief(user: User) -> dict:
    """用户基础资料（PATCH/DELETE 后复用，避免全量聚合）"""
    return {
        "id": user.id,
        "nickname": user.nickname or f"玩家{user.id}",
        "avatar_url": user.avatar_url or "",
        "platform": user.platform or "",
        "country_code": user.country_code or "",
        "region_code": user.region_code or "",
        "status": user.status,
    }


async def update_profile(db: AsyncSession, user_id: int, nickname: str | None, region_code: str | None, country_code: str | None) -> dict:
    """修改昵称 / 区域（A8；昵称去空白，限制长度）"""
    user = await _load_user(db, user_id)
    if nickname is not None:
        nickname = nickname.strip()
        if not nickname:
            raise ValueError("昵称不能为空")
        user.nickname = nickname[:32]
    if region_code is not None:
        user.region_code = region_code[:16]
    if country_code is not None:
        user.country_code = country_code[:4]
    await db.commit()
    await db.refresh(user)
    return _user_brief(user)


async def delete_account(db: AsyncSession, user_id: int) -> None:
    """账号注销（A8/I1：合规删除本人全部数据，含流水与埋点）"""
    user = await _load_user(db, user_id)

    # 子表数据全部删除（含外键引用方），最后删用户行
    for model in (Record, WalletLog, Wallet, UserProp, PlayerDaily, CheatLog, GameEvent, Order, UserCosmetic):
        await db.execute(
            delete(model).where(model.user_id == user_id)
        )
    # 好友关系双向清理（涉及 user_id / friend_id 两列）
    await db.execute(
        delete(UserRelation).where(
            (UserRelation.user_id == user_id) | (UserRelation.friend_id == user_id)
        )
    )
    await db.delete(user)
    await db.commit()
    logger.info(f"[account] user_id={user_id} 账号已注销删除")


async def get_player_summary(db: AsyncSession, user_id: int) -> dict:
    """聚合返回用户资料 + 累计统计 + 道具/钱包余额

    stats 从 hd_player_daily 汇总（权威源，已含 win/fail/quit 全部对局），
    per-level best 来自 hd_records 的最小通关时间。
    """
    user = await _load_user(db, user_id)

    # 累计统计（对局数/时长/通关数 —— 全部由每日汇总表滚动而来）
    daily_agg = (
        select(
            sa_func.coalesce(sa_func.sum(PlayerDaily.games), 0).label("total_games"),
            sa_func.coalesce(sa_func.sum(PlayerDaily.wins), 0).label("total_wins"),
            sa_func.coalesce(sa_func.sum(PlayerDaily.play_seconds), 0.0).label("total_play_seconds"),
        )
        .where(PlayerDaily.user_id == user_id)
    )
    agg_row = (await db.execute(daily_agg)).one()

    # 每关最快成绩
    best_stmt = (
        select(Record.level_id, sa_func.min(Record.clear_time).label("best"))
        .where(Record.user_id == user_id)
        .group_by(Record.level_id)
    )
    best_rows = (await db.execute(best_stmt)).all()
    best_by_level = {row.level_id: round(row.best, 2) for row in best_rows}

    # 道具余额（缺省补 0）
    props_stmt = select(UserProp).where(UserProp.user_id == user_id)
    prop_rows = (await db.execute(props_stmt)).scalars().all()
    props = {k: 0 for k in KNOWN_PROP_KEYS}
    for row in prop_rows:
        props[row.prop_key] = row.balance

    # 钱包余额（缺省补 0）
    wallet_stmt = select(Wallet).where(Wallet.user_id == user_id)
    wallet_rows = (await db.execute(wallet_stmt)).scalars().all()
    wallet = {k: 0 for k in KNOWN_CURRENCIES}
    for row in wallet_rows:
        if row.currency in wallet:
            wallet[row.currency] = row.balance

    return {
        "user": {
            "id": user.id,
            "nickname": user.nickname or f"玩家{user.id}",
            "avatar_url": user.avatar_url or "",
            "platform": user.platform or "",
            "country_code": user.country_code or "",
            "region_code": user.region_code or "",
            "status": user.status,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "stats": {
            "total_games": int(agg_row.total_games),
            "total_wins": int(agg_row.total_wins),
            "total_play_seconds": round(float(agg_row.total_play_seconds), 1),
            "best_by_level": best_by_level,
        },
        "props": props,
        "wallet": wallet,
    }
