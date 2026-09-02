"""远端关卡 API（D1）"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.level import LevelSaveRequest
from app.services import level_service
from app.utils.response import success
from app.api.admin import require_admin

router = APIRouter(prefix="/api/levels", tags=["关卡配置"])


@router.get("")
async def list_levels(db: AsyncSession = Depends(get_db)):
    """启用关卡列表（客户端开局前拉取；含布局 JSON）"""
    items = await level_service.get_enabled_levels(db)
    return success(data={"items": items})


@router.put("/{level_id}")
async def save_level(
    level_id: int,
    req: LevelSaveRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """后台保存/更新关卡布局（编辑器或脚本调用）"""
    data = await level_service.save_level(db, level_id, req.title, req.icon_types, req.layout, req.remark)
    return success(data=data)
