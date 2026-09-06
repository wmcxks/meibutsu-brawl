"""装扮 API（C5：目录 / 购买(gem) / 装备）

目录无需登录；购买/装备需登录。装备成功的主题由前端在启动时生效
（本地缓存 hd_theme，下次进游戏使用新卡面）。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.schemas.cosmetic import CosmeticRequest
from app.services import cosmetic_service, player_service
from app.utils.response import success, error

router = APIRouter(prefix="/api/cosmetics", tags=["装扮"])


@router.get("/catalog")
async def catalog(db: AsyncSession = Depends(get_db)):
    """装扮目录（无需登录，不返回拥有态）"""
    return success(data=await cosmetic_service.list_catalog(db, None))


@router.get("/mine")
async def mine(user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """我的装扮与装备态（启动时拉取，同步主题）"""
    return success(data=await cosmetic_service.mine(db, user_id))


@router.post("/buy")
async def buy(
    req: CosmeticRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """gem 购买装扮（扣钱包账本；余额不足 400；买即装备）"""
    try:
        await player_service.assert_user_active(db, user_id)
        return success(data=await cosmetic_service.buy(db, user_id, req.item_key))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        return error(message=str(e))


@router.post("/equip")
async def equip(
    req: CosmeticRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """装备已拥有装扮（免费默认款 / 已购均可）"""
    try:
        await player_service.assert_user_active(db, user_id)
        return success(data=await cosmetic_service.equip(db, user_id, req.item_key))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        return error(message=str(e))
