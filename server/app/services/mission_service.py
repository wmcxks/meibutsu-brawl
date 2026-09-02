"""任务业务（A7）

进度口径与 hd_player_daily 完全一致（不重复计数）：
  - daily    周期 = 今天（UTC）
  - weekly   周期 = 本 ISO 周
  - achievement 周期 = 终身累计
领取：hd_user_missions 唯一键 (user_id, mission_key, period) 保证幂等，
奖励发放走 C1（placement=mission:reward，跳过 nonce 与每日上限）。
"""

import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mission import MissionTemplate, UserMission
from app.models.player_daily import PlayerDaily
from app.services import reward_service

logger = logging.getLogger(__name__)

VALID_SCOPES = {"daily", "weekly", "achievement"}


def period_of(scope: str) -> tuple[str, date, date]:
    """计算当前周期标识与起止日（UTC）"""
    today = datetime.now(timezone.utc).date()
    if scope == "daily":
        return today.isoformat(), today, today
    if scope == "weekly":
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        iso = today.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}", monday, sunday
    # achievement：终身
    return "all", date.min, date.max


def _load_claim(scope: str) -> tuple[str, date, date]:
    return period_of(scope)


async def _progress(db: AsyncSession, user_id: int, template: MissionTemplate, start: date, end: date) -> int:
    """按模板口径聚合进度（login_days 记不同活跃日数）"""
    stmt = select(
        sa_func.coalesce(sa_func.sum(PlayerDaily.games), 0),
        sa_func.coalesce(sa_func.sum(PlayerDaily.wins), 0),
        sa_func.coalesce(sa_func.sum(PlayerDaily.play_seconds), 0.0),
        sa_func.count(sa_func.distinct(PlayerDaily.stat_date)),
    ).where(PlayerDaily.user_id == user_id, PlayerDaily.stat_date >= start, PlayerDaily.stat_date <= end)
    games, wins, seconds, active_days = (await db.execute(stmt)).one()

    if template.target_type == "games":
        return int(games)
    if template.target_type == "wins":
        return int(wins)
    if template.target_type == "play_minutes":
        return int(seconds // 60)
    if template.target_type == "login_days":
        return int(active_days)
    return 0


async def list_missions(db: AsyncSession, user_id: int, scope: str) -> list[dict]:
    """列出某周期全部启用任务 + 用户进度/领取状态"""
    if scope not in VALID_SCOPES:
        raise HTTPException(status_code=400, detail="未知的任务周期")

    period, start, end = period_of(scope)
    stmt = (
        select(MissionTemplate)
        .where(MissionTemplate.scope == scope, MissionTemplate.enabled.is_(True))
        .order_by(MissionTemplate.sort_order.asc(), MissionTemplate.mission_key.asc())
    )
    templates = (await db.execute(stmt)).scalars().all()

    claimed_stmt = select(UserMission.mission_key).where(
        UserMission.user_id == user_id,
        UserMission.period == period,
    )
    claimed_keys = set((await db.execute(claimed_stmt)).scalars().all())

    items = []
    for t in templates:
        progress = await _progress(db, user_id, t, start, end)
        items.append(
            {
                "mission_key": t.mission_key,
                "scope": t.scope,
                "period": period,
                "title": t.title,
                "target_type": t.target_type,
                "target_value": t.target_value,
                "progress": progress,
                "completed": progress >= t.target_value,
                "claimed": t.mission_key in claimed_keys,
                "reward_prop_key": t.reward_prop_key,
                "reward_amount": t.reward_amount,
            }
        )
    return items


async def claim_mission(db: AsyncSession, user_id: int, mission_key: str, period: str) -> dict:
    """领取任务奖励（唯一键幂等；进度未达标/重复领取返回明确错误）"""
    template = await db.get(MissionTemplate, mission_key)
    if template is None or not template.enabled:
        raise HTTPException(status_code=404, detail="任务不存在或未启用")

    # 校验 period 与模板周期匹配，防止用过期周期刷任务
    expect_period, start, end = period_of(template.scope)
    if period != expect_period:
        raise HTTPException(status_code=400, detail="任务周期不匹配")

    exists = await db.get(UserMission, (user_id, mission_key, period))
    if exists is not None:
        raise HTTPException(status_code=409, detail="该任务已领取")

    progress = await _progress(db, user_id, template, start, end)
    if progress < template.target_value:
        raise HTTPException(status_code=400, detail="任务尚未完成")

    # 先占领取位（本表唯一键即幂等闸门），再走 C1 发放
    db.add(UserMission(user_id=user_id, mission_key=mission_key, period=period))
    await db.commit()

    reward = await reward_service.grant_prop(
        db, user_id, "mission:reward", template.reward_prop_key,
        template.reward_amount, skip_nonce=True,
    )
    logger.info(f"[mission] user_id={user_id} claim {mission_key}@{period} reward={reward}")
    return {"claimed": True, "mission_key": mission_key, "period": period, "reward": reward}
