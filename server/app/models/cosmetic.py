"""装扮商品模型（C5：主题/卡背等付费外观）

- hd_cosmetics   商品目录（迁移种子维护；kind=theme 对应前端 CARD_THEMES）
- hd_user_cosmetics 用户拥有/装备（同 kind 仅一件装备；price=0 免费默认不落库）
"""

from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, SmallInteger, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Cosmetic(Base):
    """装扮目录（模板层，迁移/后台维护）"""

    __tablename__ = "hd_cosmetics"

    item_key: Mapped[str] = mapped_column(String(48), primary_key=True, comment="商品键（theme 名 / cardback 名）")
    kind: Mapped[str] = mapped_column(String(16), comment="类别：theme / cardback / ...")
    name: Mapped[str] = mapped_column(String(64), default="", comment="商品名（客户端展示文案）")
    price_gem: Mapped[int] = mapped_column(Integer, default=0, comment="售价（gem；0 = 免费默认款）")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否上架")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    extra: Mapped[str] = mapped_column(Text, nullable=True, comment="附加 JSON（如 iconCount）")
    remark: Mapped[str] = mapped_column(String(128), default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class UserCosmetic(Base):
    """用户拥有的装扮（PK 保证重复购买幂等；equipped 每次仅同 kind 一件置 1）"""

    __tablename__ = "hd_user_cosmetics"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("hd_users.id"), primary_key=True, comment="用户ID")
    item_key: Mapped[str] = mapped_column(String(48), ForeignKey("hd_cosmetics.item_key"), primary_key=True, comment="商品键")
    equipped: Mapped[int] = mapped_column(SmallInteger, default=0, comment="0 未装备 / 1 已装备")
    acquired_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="获得时间")
