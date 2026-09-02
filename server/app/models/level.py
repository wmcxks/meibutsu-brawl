"""远端关卡模型（D1：布局配置化下发，不发版周更）"""

from datetime import datetime

from sqlalchemy import Integer, Boolean, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Level(Base):
    """关卡配置（layout 为 RegionConfig[] 的 JSON）

    结构对齐前端 types/game.ts：
      layout: [{x, y, layers: [{layer, gapRatio, offsetCol?, offsetRow?, cards: [{col, row}]}]}]
    """
    __tablename__ = "hd_levels"

    level_id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="关卡ID（1 起）")
    title: Mapped[str] = mapped_column(String(64), default="", comment="关卡标题")
    icon_types: Mapped[int] = mapped_column(Integer, default=12, comment="本关使用的图标种类数")
    layout: Mapped[str] = mapped_column(Text, comment="棋盘布局 JSON（RegionConfig[]）")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="配置版本（每次更新 +1）")
    remark: Mapped[str] = mapped_column(String(128), default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
