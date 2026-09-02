"""管理后台 Schema（G1）"""

from pydantic import BaseModel, Field


class AdminCompensateRequest(BaseModel):
    """运营补偿（走 /api/rewards 同一发放逻辑，跳过渠道上限）"""

    user_id: int = Field(description="目标用户ID")
    prop_key: str = Field(min_length=1, max_length=32, description="道具键（move_out / undo / shuffle / peek）")
    amount: int = Field(ge=1, le=999, description="发放数量（运营场景可大于玩家侧上限）")
    nonce: str = Field(default="", max_length=64, description="幂等令牌（可留空，服务端自动生成）")
    remark: str = Field(default="", max_length=128, description="补偿原因备注")


class AdminSetConfigRequest(BaseModel):
    """写入远端配置"""

    value: object = Field(description="配置值（JSON 可序列化）")
    remark: str = Field(default="", max_length=128, description="备注")


class AdminBanRequest(BaseModel):
    """封禁/解封"""

    status: int = Field(ge=0, le=1, description="0 = 解封 / 1 = 封禁")
    reason: str = Field(default="", max_length=256, description="原因（建议写，便于审计）")
