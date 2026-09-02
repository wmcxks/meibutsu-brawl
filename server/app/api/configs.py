"""远端配置公共 API（A6/G2：客户端可见配置）"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import config_service
from app.utils.response import success

router = APIRouter(prefix="/api/configs", tags=["远端配置"])


@router.get("/public")
async def get_public_configs(db: AsyncSession = Depends(get_db)):
    """客户端可见配置（白名单：当前含公告等）"""
    data = await config_service.get_public(db)
    return success(data=data)
