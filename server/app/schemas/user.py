"""玩家信息 Schema（A8：资料修改 / 账号注销）"""

from pydantic import BaseModel, Field


class UserUpdateRequest(BaseModel):
    """修改资料请求（均可选，未传字段保持不变）"""

    nickname: str | None = Field(default=None, min_length=1, max_length=32, description="昵称")
    region_code: str | None = Field(default=None, max_length=16, description="区域码（如 jp-13）")
    country_code: str | None = Field(default=None, max_length=4, description="国家/地区码（ISO 3166-1 alpha-2）")


class AccountDeleteRequest(BaseModel):
    """注销确认（防止误触）"""

    confirm: bool = Field(description="必须为 true 才执行删除")
