"""订单与支付凭证模型（C3：商店/订单通用层，渠道适配器接入前先行）"""

from datetime import datetime

from sqlalchemy import Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Order(Base):
    """商品订单（状态机 pending → paid / cancelled）

    - 渠道支付接入前：pending 订单由运营后台确认收款后 mark-paid（测试/代收）
    - 接入 LINE Pay / 商店后：回调验签通过后置 paid，发货逻辑不变
    - 发货走钱包账本（event_type=purchase, event_id=order_no，幂等）
    """
    __tablename__ = "hd_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(40), unique=True, comment="订单号（业务幂等键）")
    user_id: Mapped[int] = mapped_column(Integer, index=True, comment="用户ID")
    sku: Mapped[str] = mapped_column(String(48), comment="商品 SKU（与商品目录一致）")
    currency: Mapped[str] = mapped_column(String(8), comment="发放币种（gem / coin）")
    amount: Mapped[int] = mapped_column(Integer, comment="发放数量")
    status: Mapped[str] = mapped_column(String(12), default="pending", comment="pending / paid / cancelled")
    channel: Mapped[str] = mapped_column(String(16), default="manual", comment="支付渠道：manual / line_pay / ...")
    provider_receipt: Mapped[str] = mapped_column(String(512), default="", comment="渠道回执/交易号（验签后记录）")
    remark: Mapped[str] = mapped_column(String(128), default="", comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    paid_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, comment="支付/发货时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
