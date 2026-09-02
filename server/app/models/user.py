"""用户模型"""

from datetime import datetime

from sqlalchemy import String, SmallInteger, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "hd_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    openid: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="平台用户标识（guest:/line: 前缀命名空间）")
    nickname: Mapped[str] = mapped_column(String(128), default="", comment="昵称")
    avatar_url: Mapped[str] = mapped_column(String(512), default="", comment="头像地址")

    # ── V2 商业版：画像字段 ──
    platform: Mapped[str] = mapped_column(String(16), default="", comment="注册平台（web / line）")
    client_ver: Mapped[str] = mapped_column(String(32), default="", comment="最近登录客户端版本")
    country_code: Mapped[str] = mapped_column(String(4), default="", comment="国家/地区码（ISO 3166-1 alpha-2）")
    region_code: Mapped[str] = mapped_column(String(16), default="", comment="区域码（日本都道府県 JIS X 0401，如 jp-13）")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, comment="账号状态：0 正常 / 1 封禁")
    first_login_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="首次登录时间")
    last_login_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="最近登录时间")
    login_count: Mapped[int] = mapped_column(Integer, default=0, comment="累计登录次数")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
