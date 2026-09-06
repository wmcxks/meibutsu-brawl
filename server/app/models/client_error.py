"""客户端错误上报模型（F3：前端崩溃/JS 错误采集）"""

from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClientError(Base):
    """前端错误（window.onerror / unhandledrejection / Phaser 运行时错误）

    - user_id = -1 表示未登录（与 hd_events 口径一致，不阻断上报）
    - extras 存扁平 JSON（平台/客户端版本/页面 URL 等附加信息）
    """
    __tablename__ = "hd_client_errors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=-1, comment="用户ID（-1 未登录）")
    platform: Mapped[str] = mapped_column(String(16), default="", comment="平台（web / line）")
    client_ver: Mapped[str] = mapped_column(String(32), default="", comment="客户端版本")
    page_url: Mapped[str] = mapped_column(String(512), default="", comment="页面 URL（去 query）")
    message: Mapped[str] = mapped_column(String(512), default="", comment="错误摘要")
    stack: Mapped[str] = mapped_column(Text, nullable=True, comment="错误堆栈（可能含源码路径）")
    extras: Mapped[str] = mapped_column(Text, nullable=True, comment="附加 JSON（props 等）")
    client_ts: Mapped[int] = mapped_column(Integer, default=0, comment="客户端秒级时间戳")
    acknowledged: Mapped[int] = mapped_column(SmallInteger, default=0, comment="0 未处理 / 1 已确认")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="接收时间")
