"""埋点事件 Schema（F1）"""

from pydantic import BaseModel, Field, field_validator


class EventItem(BaseModel):
    """单条事件"""

    event: str = Field(min_length=1, max_length=48, pattern=r"^[a-z][a-z0-9_]{0,47}$", description="事件名（page_load / level_start / level_win / ...）")
    props: dict = Field(default_factory=dict, description="事件属性（扁平 JSON，长度受限）")
    client_ts: int = Field(default=0, description="客户端秒级时间戳")

    @field_validator("props")
    @classmethod
    def _props_size(cls, v: dict) -> dict:
        # 属性 JSON 长度上限 1KB，超长事件丢弃而不是拖垮接口
        if len(str(v)) > 1024:
            raise ValueError("props 过大")
        return v


class EventsBatchRequest(BaseModel):
    """批量上报（单次上限 50 条）"""

    events: list[EventItem]

    @field_validator("events")
    @classmethod
    def _batch_size(cls, v: list) -> list:
        if len(v) > 50:
            raise ValueError("单次最多上报 50 条")
        return v
