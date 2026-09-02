"""埋点事件模型（F1：一切漏斗/留存/经济决策的数据源）"""

from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GameEvent(Base):
    """统一埋点事件表。字段名小写、JSON 扁平，聚合时按事件名过滤。"""
    __tablename__ = "hd_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, comment="用户ID（-1 表示未登录）")
    event: Mapped[str] = mapped_column(String(48), index=True, comment="事件名（page_load / level_start / level_win / ...）")
    props: Mapped[str] = mapped_column(Text, default="{}", comment="事件属性 JSON（level_id / clear_time / outcome 等）")
    client_ts: Mapped[float] = mapped_column(Integer, default=0, comment="客户端秒级时间戳（可选）")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="接收时间")
