"""登录鉴权相关 Schema"""

from pydantic import BaseModel, Field


class LoginProfile(BaseModel):
    """登录时可携带的用户画像信息（可选，登录时落库/更新）"""

    platform: str = Field(default="", max_length=16, description="平台标识（web / line）")
    client_ver: str = Field(default="", max_length=32, description="客户端版本")
    country_code: str = Field(default="", max_length=4, description="国家/地区码（ISO 3166-1 alpha-2）")
    region_code: str = Field(default="", max_length=16, description="区域码（如 jp-13）")


class GuestLoginRequest(LoginProfile):
    """H5 游客静默登录请求"""
    guest_uuid: str = Field(min_length=1, max_length=64, description="前端生成的游客唯一标识")


class LineLoginRequest(LoginProfile):
    """LINE LIFF 登录请求"""
    id_token: str = Field(min_length=1, description="LIFF 登录后获取的 id_token")
