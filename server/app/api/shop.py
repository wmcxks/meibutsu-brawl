"""商店 API（C3：商品目录 / 下单 / 后台确认发货）"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.schemas.shop import OrderCreateRequest, MarkPaidRequest
from app.services import order_service, player_service
from app.utils.response import success
from app.models.order import Order
from app.api.admin import require_admin

router = APIRouter(prefix="/api/shop", tags=["商店"])


@router.get("/products")
async def list_products():
    """商品目录（无需登录）"""
    return success(data={"items": order_service.get_products()})


@router.post("/order")
async def create_order(
    req: OrderCreateRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """下单（生成 pending 订单；支付渠道接入前由后台确认收款发货）"""
    try:
        await player_service.assert_user_active(db, user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return success(data=await order_service.create_order(db, user_id, req.sku))


@router.post("/order/cancel")
async def cancel_order(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """取消我的待支付订单"""
    return success(data=await order_service.cancel_pending(db, user_id))


@router.post("/admin/orders/{order_no}/mark-paid")
async def mark_order_paid(
    order_no: str,
    req: MarkPaidRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """后台确认收款并发货（代收/测试；接渠道后由回调调用同一发货逻辑）"""
    data = await order_service.mark_paid(db, order_no, req.provider_receipt, req.channel)
    return success(data=data)


@router.get("/admin/orders")
async def list_orders(
    _: None = Depends(require_admin),
    status: str = Query(default="pending", description="pending / paid / cancelled / all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """后台订单列表"""
    from sqlalchemy import func as sa_func

    conditions = []
    if status != "all":
        conditions.append(Order.status == status)
    total = (await db.execute(select(sa_func.count(Order.id)).where(*conditions))).scalar_one()
    stmt = (
        select(Order)
        .where(*conditions)
        .order_by(Order.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "order_no": o.order_no,
            "user_id": o.user_id,
            "sku": o.sku,
            "currency": o.currency,
            "amount": o.amount,
            "status": o.status,
            "channel": o.channel,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        }
        for o in rows
    ]
    return success(data={"total": total, "items": items})
