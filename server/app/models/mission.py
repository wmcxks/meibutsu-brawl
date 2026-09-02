"""任务体系模型（A7：签到 / 每日 / 周 / 成就 共用结构）"""

from datetime import datetime

from sqlalchemy import Integer, Boolean, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MissionTemplate(Base):
    """任务模板（配置层，由迁移/后台维护）

    scope: daily（周期=自然日）/ weekly（周期=自然周）/ achievement（终身一次）
    target_type 与 hd_player_daily 对齐，进度实时计算，不重复写计数器：
      games / wins / play_minutes / login_days
    """
    __tablename__ = "hd_mission_templates"

    mission_key: Mapped[str] = mapped_column(String(48), primary_key=True, comment="任务键（唯一）")
    scope: Mapped[str] = mapped_column(String(16), default="daily", comment="周期：daily / weekly / achievement")
    title: Mapped[str] = mapped_column(String(64), default="", comment="任务标题（客户端展示文案）")
    target_type: Mapped[str] = mapped_column(String(24), comment="进度口径：games / wins / play_minutes / login_days")
    target_value: Mapped[int] = mapped_column(Integer, comment="目标值")
    reward_prop_key: Mapped[str] = mapped_column(String(32), comment="奖励道具键")
    reward_amount: Mapped[int] = mapped_column(Integer, default=1, comment="奖励数量")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    remark: Mapped[str] = mapped_column(String(128), default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class UserMission(Base):
    """用户任务进度 / 领取记录（领取态由唯一键保证幂等）

    period: daily=YYYY-MM-DD / weekly=YYYY-Www / achievement=all
    """
    __tablename__ = "hd_user_missions"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="用户ID")
    mission_key: Mapped[str] = mapped_column(String(48), primary_key=True, comment="任务键")
    period: Mapped[str] = mapped_column(String(16), primary_key=True, comment="任务周期（UTC）")
    claimed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="领取时间")
