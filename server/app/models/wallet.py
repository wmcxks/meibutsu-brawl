"""钱包（多币种余额）模型（A4）"""

from datetime import datetime

from sqlalchemy import Integer, BigInteger, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Wallet(Base):
    """用户多币种余额：currency ∈ {coin, gem, ...}

    任何余额变动必须同时写 hd_wallet_logs 流水（幂等 event_id），
    严禁在业务代码里散落 UPDATE。
    """
    __tablename__ = "hd_wallets"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("hd_users.id"), primary_key=True, comment="用户ID")
    currency: Mapped[str] = mapped_column(String(16), primary_key=True, comment="币种：coin / gem")
    balance: Mapped[int] = mapped_column(BigInteger, default=0, comment="余额")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class WalletLog(Base):
    """钱包流水（只增不改，用于对账/审计/补发）"""

    __tablename__ = "hd_wallet_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("hd_users.id"), index=True, comment="用户ID")
    currency: Mapped[str] = mapped_column(String(16), comment="币种")
    delta: Mapped[int] = mapped_column(BigInteger, comment="变动量（正=收入，负=支出）")
    balance_after: Mapped[int] = mapped_column(BigInteger, comment="变动后余额")
    event_type: Mapped[str] = mapped_column(String(48), comment="变动类型（reward / purchase / consume / refund）")
    event_id: Mapped[str] = mapped_column(String(64), unique=True, comment="幂等事件ID（同一奖励只生效一次）")
    detail: Mapped[str] = mapped_column(String(512), default="", comment="详情（placement / 订单号等）")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="流水时间")
