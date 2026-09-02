"""任务相关 Schema（A7）"""

from pydantic import BaseModel, Field


class MissionClaimRequest(BaseModel):
    """领取任务奖励"""

    mission_key: str = Field(min_length=1, max_length=48, description="任务键")
    period: str = Field(min_length=4, max_length=16, description="任务周期（列表接口返回的 period 原样回传）")
