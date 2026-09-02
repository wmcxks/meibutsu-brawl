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
from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库与 Redis 连接"""
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

# 注册路由
app.include_router(auth_router)
app.include_router(record_router)
app.include_router(user_router)
app.include_router(rewards_router)
app.include_router(events_router)
app.include_router(admin_router)
app.include_router(missions_router)


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
