"""通关记录相关 Schema"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RecordStartRequest(BaseModel):
    """开局请求"""
    level_id: int = Field(description="关卡ID")


class RecordSubmit(BaseModel):
    """结算请求（win / fail / quit 统一走此接口）

    clear_time 语义：本局用时（秒）。win 时同时用于排行榜成绩；
    fail/quit 时仅作时长统计，服务端会用 Redis 会话真实经过时间校验上限。
    """
    level_id: int
    clear_time: float  # 本局用时（秒）
    outcome: Literal["win", "fail", "quit"] = "win"
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
