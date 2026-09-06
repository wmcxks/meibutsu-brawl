"""监控中间件（F3）：统计每个请求耗时/状态码，慢请求与错误率走 monitor_service 告警"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.middleware.auth_middleware import decode_token
from app.services import monitor_service

logger = logging.getLogger(__name__)


def _user_id_from_request(request: Request) -> int | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        return decode_token(auth[7:]).get("user_id")
    except Exception:
        return None


class MonitorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        user_id = _user_id_from_request(request)
        try:
            response = await call_next(request)
        except Exception:
            duration = (time.monotonic() - start) * 1000
            monitor_service.record(duration, request.url.path, 500, user_id)
            raise
        duration = (time.monotonic() - start) * 1000
        monitor_service.record(duration, request.url.path, response.status_code, user_id)
        return response
