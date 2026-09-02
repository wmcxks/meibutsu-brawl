"""远端关卡 Schema（D1）"""

from pydantic import BaseModel, Field


class LevelSaveRequest(BaseModel):
    """保存关卡（布局须为 RegionConfig[] JSON 结构）"""

    title: str = Field(default="", max_length=64, description="关卡标题")
    icon_types: int = Field(default=12, ge=1, le=30, description="图标种类数")
    layout: list = Field(description="棋盘布局（RegionConfig[]）")
    remark: str = Field(default="", max_length=128, description="备注")
