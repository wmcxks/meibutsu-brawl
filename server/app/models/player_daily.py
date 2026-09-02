"""玩家每日汇总表模型（A3：时长/留存/疲劳管控的唯一权威来源）"""

from datetime import date, datetime

from sqlalchemy import Date, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlayerDaily(Base):
    """按 用户×UTC日 聚合：游戏时长、局数、通关数、广告/奖励数。

    数据在每次结算（win/fail/quit）与奖励发放时累加；
    留存/DAU/疲劳管控等运营指标均从本表出，不直查流水表。
    """
    __tablename__ = "hd_player_daily"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("hd_users.id"), primary_key=True, comment="用户ID")
    stat_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="统计日（UTC）")
    play_seconds: Mapped[float] = mapped_column(Float, default=0, comment="当日游戏时长（秒，服务端按会话真实经过时间累计）")
    games: Mapped[int] = mapped_column(Integer, default=0, comment="当日对局数（含失败/中途退出）")
    wins: Mapped[int] = mapped_column(Integer, default=0, comment="当日通关局数")
    ads_watched: Mapped[int] = mapped_column(Integer, default=0, comment="当日观看激励广告次数")
    rewards: Mapped[int] = mapped_column(Integer, default=0, comment="当日获得奖励次数（广告/分享/运营）")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="首次创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="最近更新时间")
