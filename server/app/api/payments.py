"""支付渠道回调 API（C3：LINE Pay 等真实渠道验签入口）

- 公开接口（渠道服务端回调，无用户态），验签依赖渠道签名而非鉴权
- 验签通过 → resolve 订单 → order_service.mark_paid 同一发货路径
- 渠道未配置凭据时返回 501；验签失败返回 403（并记日志告警）
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import order_service
from app.services.payments import (
    NotConfigured,
    PaymentVerificationError,
    get_provider,
    resolve_order,
)
from app.utils.response import success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["支付回调"])


@router.post("/{provider}/callback")
async def payment_callback(provider: str, request: Request, db: AsyncSession = Depends(get_db)):
    """渠道支付结果回调（raw body 原样收取供验签）"""
    adapter = get_provider(provider)
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    try:
        info = await adapter.verify(raw_body, headers)
    except NotConfigured as e:
        logger.warning(f"[payment:{provider}] 回调到达但渠道未配置: {e}")
        return JSONResponse(status_code=501, content=success(data=None, message=str(e)))
    except PaymentVerificationError as e:
        logger.warning(f"[payment:{provider}] 验签失败: {e}")
        return JSONResponse(status_code=403, content=success(data=None, message="签名校验失败"))

    try:
        order = await resolve_order(db, info)
        data = await order_service.mark_paid(
            db, order.order_no,
            provider_receipt=info.get("transaction_id", "")[:512],
            channel=adapter.name,
        )
        logger.info(f"[payment:{provider}] 回调发货成功 order_no={order.order_no}")
        return success(data=data)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content=success(data=None, message=e.detail))
