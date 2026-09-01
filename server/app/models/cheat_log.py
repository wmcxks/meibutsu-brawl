"""作弊日志模型"""

from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CheatLog(Base):
    __tablename__ = "hd_cheat_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("hd_users.id"), index=True, comment="用户ID")
    session_id: Mapped[str] = mapped_column(String(64), default="", comment="开局会话ID")
    level_id: Mapped[int] = mapped_column(Integer, default=0, comment="关卡ID")
    reason: Mapped[str] = mapped_column(String(64), comment="作弊原因（level_mismatch / impossible_time / too_fast）")
    detail: Mapped[str] = mapped_column(String(512), default="", comment="详情（如 clear_time / elapsed）")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="记录时间")
