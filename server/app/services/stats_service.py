"""玩家每日统计业务（A3/B1/B2：时长与对局数权威累计源）"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.player_daily import PlayerDaily

logger = logging.getLogger(__name__)


async def record_outcome(
    db: AsyncSession,
    user_id: int,
    level_id: int,
    outcome: str,
    duration: float,
) -> None:
    """结算一次对局：累加当日 games/wins/play_seconds（UTC 日）

    - outcome: win / fail / quit
    - duration: 服务端校验/收敛后的本局用时（秒，≤ 会话真实经过时间）
    - level_id 暂不细化到每日表（如需按关分析，加列或查 hd_records）
    """
    today = datetime.now(timezone.utc).date()
    stmt = select(PlayerDaily).where(
        PlayerDaily.user_id == user_id,
        PlayerDaily.stat_date == today,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()

    if row is None:
        row = PlayerDaily(
            user_id=user_id,
            stat_date=today,
            games=1,
            wins=1 if outcome == "win" else 0,
            play_seconds=duration,
        )
        db.add(row)
    else:
        row.games = (row.games or 0) + 1
        if outcome == "win":
            row.wins = (row.wins or 0) + 1
        row.play_seconds = (row.play_seconds or 0) + duration

    await db.commit()
    logger.info(
        f"[stats] user_id={user_id} level_id={level_id} outcome={outcome} "
        f"duration={duration:.1f}s date={today}"
    )
