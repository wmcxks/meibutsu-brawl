"""装扮 Schema（C5）"""

from pydantic import BaseModel, Field


class CosmeticRequest(BaseModel):
    """购买/装备请求"""

    item_key: str = Field(min_length=1, max_length=48, description="装扮商品键")
