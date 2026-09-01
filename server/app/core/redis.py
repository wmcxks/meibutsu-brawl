"""Redis 异步客户端（会话防作弊 / 限频）"""

import logging
from urllib.parse import quote, urlparse

from redis import asyncio as aioredis

from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


def _build_redis_url() -> str:
    """由分段配置组装连接串（REDIS_USERNAME / HOST / PORT / PASSWORD / DB）。

    TLS（rediss://）判定优先级：
      1. REDIS_SSL=true 强制启用；
      2. REDIS_HOST 带 rediss:// 或 https:// 前缀（Upstash 控制台 REST 地址形态）；
      3. host 含 .upstash.io（Upstash 强制 TLS，否则服务端直接断开）。
    其余情况走明文 redis://（本地开发）。
    """
    scheme = "redis"
    host = settings.REDIS_HOST
    username = settings.REDIS_USERNAME
    password = settings.REDIS_PASSWORD

    if settings.REDIS_SSL:
        scheme = "rediss"
    elif host.startswith("rediss://") or host.startswith("redis://") or host.startswith("https://"):
        parsed = urlparse(host)
        # https:// 形态是 Upstash 控制台地址，Redis 侧仍走 TLS（rediss）
        scheme = "rediss" if parsed.scheme in ("rediss", "https") else "redis"
        if parsed.hostname:
            host = parsed.hostname
        if parsed.username:
            username = parsed.username
        if parsed.password:
            password = parsed.password
    elif ".upstash.io" in host:
        scheme = "rediss"

    # 密码含特殊字符时做 URL 编码，避免连接串解析错误
    creds = f"{quote(username)}:{quote(password)}@" if password else ""
    return f"{scheme}://{creds}{host}:{settings.REDIS_PORT}/{settings.REDIS_DB}"


# from_url 自动识别 rediss:// 并启用 SSL（Upstash 等云 Redis 需要）
redis_client = aioredis.from_url(_build_redis_url(), decode_responses=True)


async def init_redis():
    """启动时探测连接，失败仅告警不阻断（与 MySQL 策略一致）"""
    try:
        await redis_client.ping()
        logger.info("Redis 连接成功")
    except Exception as e:
        logger.warning(f"Redis 连接失败，防刷功能不可用: {e}")


async def close_redis():
    try:
        await redis_client.aclose()
    except Exception as e:
        logger.warning(f"Redis 关闭异常: {e}")
