"""奖励发放 Schema（C1：道具奖励唯一入口）"""

from pydantic import BaseModel, Field


class RewardGrantRequest(BaseModel):
    """发放请求

    - placement：渠道标识（广告/分享/运营补偿），用于按渠道做每日上限与归因
    - prop_key：道具键（move_out / undo / shuffle / peek）
    - amount：发放数量（单次上限 5，防异常请求一次刷爆）
    - nonce：幂等令牌（客户端每次展示奖励前生成，服务端 7 天内拒绝重复）
    """
    placement: str = Field(min_length=1, max_length=48, description="奖励渠道（ad:reward / share:invite / op:compensation）")
    prop_key: str = Field(min_length=1, max_length=32, description="道具键")
    amount: int = Field(default=1, ge=1, le=5, description="发放数量（1~5）")
    nonce: str = Field(min_length=8, max_length=64, description="幂等令牌（同一奖励只生效一次）")
