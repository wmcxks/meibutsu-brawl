"""远端配置表模型（A6：数值/开关不发版热更新）"""

from datetime import datetime

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConfigEntry(Base):
    """KV 配置：value 存 JSON 文本（int/float/bool/str/list/dict 均可）

    - 代码内 CONFIG_DEFAULTS 兜底（配置未写库时用默认值）
    - 写库值即时生效；必要时管理端 PUT /api/admin/configs/{key} 更新
    - 敏感项（奖励系数等）不入 /api/configs/public 白名单
    """
    __tablename__ = "hd_configs"

    cfg_key: Mapped[str] = mapped_column(String(64), primary_key=True, comment="配置键（如 play.daily_max_minutes）")
    value: Mapped[str] = mapped_column(Text, comment="值（JSON 编码文本）")
    remark: Mapped[str] = mapped_column(String(128), default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
