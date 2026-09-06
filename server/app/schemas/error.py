"""客户端错误上报 Schema（F3）"""

from pydantic import BaseModel, Field


class ErrorReportRequest(BaseModel):
    """单条错误上报（字段均已限长；stack/extras 可省略）"""

    message: str = Field(min_length=1, max_length=512, description="错误摘要")
    stack: str | None = Field(default=None, max_length=8000, description="错误堆栈")
    page_url: str = Field(default="", max_length=512, description="页面 URL")
    platform: str = Field(default="", max_length=16, description="平台")
    client_ver: str = Field(default="", max_length=32, description="客户端版本")
    extras: dict | None = Field(default=None, description="附加属性（扁平 JSON）")
    client_ts: int = Field(default=0, ge=0, description="客户端秒级时间戳")
