"""名物大乱斗 — 后端服务入口"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db
from app.core.redis import init_redis, close_redis
from app.api.auth import router as auth_router
from app.api.record import router as record_router
from app.api.user import router as user_router
from app.api.rewards import router as rewards_router
from app.api.events import router as events_router
from app.api.admin import router as admin_router
from app.api.missions import router as missions_router
from app.api.shop import router as shop_router
from app.api.configs import router as configs_router
from app.api.levels import router as levels_router
from app.api.friends import router as friends_router
from app.api.errors import router as errors_router
from app.api.payments import router as payments_router
from app.api.cosmetics import router as cosmetics_router
from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库与 Redis 连接"""
    # F3 可选错误监控（Sentry；配置 SENTRY_DSN 后生效）
    from app.services.sentry_glue import init_sentry

    init_sentry()

    # 启动 — 连接失败仅告警，不阻断服务
    try:
        await init_db()
        logger.info("MySQL 连接成功")
    except Exception as e:
        logger.warning(f"MySQL 连接失败，部分功能不可用: {e}")

    await init_redis()

    yield

    await close_redis()


app = FastAPI(
    title="名物大乱斗 - 后端服务",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — 允许小游戏跨域请求
# 注意：allow_origins=["*"] 与 allow_credentials=True 并存时，
# Starlette 会回显请求来源并携带凭据头；上线后建议收敛为具体 H5 域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# F3 监控：请求耗时/状态码统计 + 慢请求与错误率告警
from app.middleware.monitor import MonitorMiddleware

app.add_middleware(MonitorMiddleware)

# 注册路由
app.include_router(auth_router)
app.include_router(record_router)
app.include_router(user_router)
app.include_router(rewards_router)
app.include_router(events_router)
app.include_router(admin_router)
app.include_router(missions_router)
app.include_router(shop_router)
app.include_router(configs_router)
app.include_router(levels_router)
app.include_router(friends_router)
app.include_router(errors_router)
app.include_router(payments_router)
app.include_router(cosmetics_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    # 直接 python main.py 启动：绑定 SERVER_HOST（默认 0.0.0.0，局域网可访问）
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG,
    )
