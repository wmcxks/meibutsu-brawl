"""好友关系 Schema（E3：邀请码互关 / 好友榜）"""

from pydantic import BaseModel, Field


class FriendBindRequest(BaseModel):
    """输入他人邀请码建立互关"""

    code: str = Field(min_length=1, max_length=16, description="对方邀请码（大小写不敏感）")
