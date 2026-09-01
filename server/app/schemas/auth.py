"""登录鉴权相关 Schema"""

from pydantic import BaseModel, Field


class GuestLoginRequest(BaseModel):
    """H5 游客静默登录请求"""
    guest_uuid: str = Field(min_length=1, max_length=64, description="前端生成的游客唯一标识")


class LineLoginRequest(BaseModel):
    """LINE LIFF 登录请求"""
    id_token: str = Field(min_length=1, description="LIFF 登录后获取的 id_token")
