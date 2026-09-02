"""玩家道具余额模型（A5：道具服务端权威）"""

from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserProp(Base):
    """用户道具存量：prop_key ∈ {move_out, undo, shuffle, peek, ...}

    替代客户端内存式 PropManager：开局下发余额、使用走 /api/props/use
    服务端扣减、奖励发放走 /api/rewards/grant（C1）。
    """
    __tablename__ = "hd_user_props"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("hd_users.id"), primary_key=True, comment="用户ID")
    prop_key: Mapped[str] = mapped_column(String(32), primary_key=True, comment="道具键（move_out / undo / shuffle / peek）")
    balance: Mapped[int] = mapped_column(Integer, default=0, comment="当前余额")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
