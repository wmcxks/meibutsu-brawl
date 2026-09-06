"""好友关系模型（E3：邀请码互关 + 好友榜）

设计：
- hd_users.invite_code 为用户唯一邀请码（懒生成，不可枚举的自定义码表）
- hd_relations 按方向存两行（A→B 与 B→A），互关 = 双向往返
- 好友榜 = 我的全部互关用户在该关最快成绩（复用 hd_records 最优口径）
"""

from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRelation(Base):
    """好友关系（每对好友存两条：A→B 与 B→A，删除需双向清理）"""

    __tablename__ = "hd_relations"
    __table_args__ = (
        UniqueConstraint("user_id", "friend_id", name="uq_rel_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("hd_users.id"), index=True, comment="关系发起方用户ID")
    friend_id: Mapped[int] = mapped_column(Integer, ForeignKey("hd_users.id"), comment="好友用户ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="结为好友时间")
