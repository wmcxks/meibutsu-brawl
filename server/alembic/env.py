"""Alembic 迁移环境（异步引擎版）

运行前提：在 server/ 目录下执行（.env / config / app 均可直接导入）。
数据库连接读取 server/.env 的 MYSQL_* 配置（与 FastAPI 应用同源）。
"""

import asyncio
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# 保证从 server/ 任意子目录执行时都能导入 config / app
SERVER_ROOT = Path(__file__).resolve().parent.parent
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import app.models  # noqa: F401  确保全部 ORM 模型注册到 Base.metadata
from app.core.database import Base  # noqa: E402
from config import get_settings  # noqa: E402

target_metadata = Base.metadata


def _database_url() -> str:
    settings = get_settings()
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL（--sql）"""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """在线模式：连接库执行迁移"""
    engine = create_async_engine(_database_url(), poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
