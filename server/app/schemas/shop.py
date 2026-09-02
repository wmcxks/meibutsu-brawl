"""商店 Schema（C3）"""

from pydantic import BaseModel, Field


class OrderCreateRequest(BaseModel):
    """下单请求"""

    sku: str = Field(min_length=1, max_length=48, description="商品 SKU")


class MarkPaidRequest(BaseModel):
    """后台确认收款（渠道/回执可选）"""

    provider_receipt: str = Field(default="", max_length=512, description="渠道回执/交易号")
    channel: str = Field(default="manual", max_length=16, description="支付渠道（manual / line_pay / ...）")
