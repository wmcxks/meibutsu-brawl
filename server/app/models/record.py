"""通关记录模型"""

from datetime import datetime

from sqlalchemy import Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Record(Base):
    __tablename__ = "hd_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("hd_users.id"), index=True, comment="用户ID")
    level_id: Mapped[int] = mapped_column(Integer, index=True, comment="关卡ID")
    clear_time: Mapped[float] = mapped_column(Float, comment="通关时间（秒）")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="记录时间")
