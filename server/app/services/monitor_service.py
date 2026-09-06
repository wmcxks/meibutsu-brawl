"""服务端监控（F3：慢请求 / 错误率告警 + 管理端概览）

- 进程内计数器（多 worker 下各自统计，概览标注"本进程"）
- 每请求结束 record()：累计请求数/5xx/慢请求/耗时
- 触发告警条件（写死阈值，读配置对象）：
    1) 单分钟内 5xx 数 >= ALERT_ERROR_PER_MINUTE  → logger.warning（含最新错误摘要）
    2) 单请求耗时 >  ALERT_SLOW_MS                → 每次 logger.warning（去 /health）
  可选 ALERT_WEBHOOK_URL：非阻塞 POST 推送到群机器人（fire-and-forget，失败仅告警）
"""

import asyncio
import logging
import time
from collections import deque

from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_counter = {"requests": 0, "errors_5xx": 0, "slow": 0, "total_ms": 0.0, "started": time.time()}
_slow_list: deque[dict] = deque(maxlen=50)
_error_list: deque[dict] = deque(maxlen=50)
# 分桶错误计数（近 2 分钟，告警窗口 1 分钟）
_error_buckets: deque[int] = deque([0] * 120, maxlen=120)
_last_alert_ts = {"error": 0.0}
_error_bucket_ts = {"ts": time.time(), "idx": 0}


def _tick() -> None:
    """按秒滚动错误桶（近似滑动窗口，不额外起定时器）"""
    now = time.time()
    while now - _error_bucket_ts["ts"] >= 1.0:
        _error_bucket_ts["ts"] += 1.0
        _error_bucket_ts["idx"] = (_error_bucket_ts["idx"] + 1) % len(_error_buckets)
        _error_buckets[_error_bucket_ts["idx"]] = 0


async def _notify_webhook(message: str) -> None:
    if not settings.ALERT_WEBHOOK_URL:
        return
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                settings.ALERT_WEBHOOK_URL,
                json={"msg_type": "text", "text": {"content": message}},
            )
    except Exception as e:
        logger.warning(f"[monitor] webhook 推送失败（忽略）: {e}")


def record(duration_ms: float, path: str, status_code: int, user_id: int | None = None) -> None:
    """每请求结束时调用一次"""
    c = _counter
    c["requests"] += 1
    c["total_ms"] += duration_ms
    if status_code >= 500:
        c["errors_5xx"] += 1
        _error_list.append({"ts": time.strftime("%H:%M:%S"), "path": path, "status": status_code, "duration_ms": round(duration_ms, 1)})
        _tick()
        _error_buckets[_error_bucket_ts["idx"]] += 1
        window = sum(_error_buckets)
        if window >= settings.ALERT_ERROR_PER_MINUTE and time.time() - _last_alert_ts["error"] >= 60:
            _last_alert_ts["error"] = time.time()
            msg = f"[monitor] 近1分钟 5xx={window} 错误率告警（阈值 {settings.ALERT_ERROR_PER_MINUTE}/min），最近: {path} {status_code}"
            logger.warning(msg)
            asyncio.create_task(_notify_webhook(msg))

    if duration_ms > settings.ALERT_SLOW_MS and not path.startswith("/health"):
        c["slow"] += 1
        _slow_list.append({"ts": time.strftime("%H:%M:%S"), "path": path, "duration_ms": round(duration_ms, 1), "user_id": user_id})
        logger.warning(f"[monitor] 慢请求 {duration_ms:.0f}ms > {settings.ALERT_SLOW_MS}ms: {path} user={user_id}")


def summary() -> dict:
    """管理端概览（本进程维度）"""
    c = _counter
    uptime = time.time() - c["started"]
    _tick()
    return {
        "uptime_seconds": round(uptime),
        "requests": c["requests"],
        "errors_5xx": c["errors_5xx"],
        "errors_5xx_last_minute": sum(_error_buckets),
        "slow_requests": c["slow"],
        "avg_duration_ms": round(c["total_ms"] / c["requests"], 1) if c["requests"] else 0.0,
        "recent_slow": list(_slow_list)[-20:],
        "recent_errors": list(_error_list)[-20:],
    }
