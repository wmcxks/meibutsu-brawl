"""通关记录相关 Schema"""

from datetime import datetime
from pydantic import BaseModel, Field


class RecordStartRequest(BaseModel):
    """开局请求"""
    level_id: int = Field(description="关卡ID")


class RecordSubmit(BaseModel):
    """提交通关记录"""
    level_id: int
    clear_time: float  # 通关时间（秒）
    session_id: str = Field(description="开局会话ID（/api/record/start 下发，防重放与防机刷）")
    timestamp: int = Field(description="前端发起请求时的秒级时间戳，用于防重放")
    sign: str = Field(description="SHA-256 签名：sha256(f\"{level_id}{clear_time}{timestamp}{ANTI_CHEAT_SALT}\")")


class RecordItem(BaseModel):
    """单条通关记录"""
    id: int
    level_id: int
    clear_time: float
    created_at: datetime

    model_config = {"from_attributes": True}


class RecordListResponse(BaseModel):
    """通关记录列表"""
    records: list[RecordItem]
