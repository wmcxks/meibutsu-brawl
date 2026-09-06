"""远端配置业务（A6）

设计：
- CONFIG_DEFAULTS：代码内兜底默认值（未写库时生效）
- 配置写库后即时生效；读路径带 30s 内存 TTL 缓存（多 worker 下最多延迟 30s 生效）
- 类型：value 一律 JSON 文本，读写统一走 json 编解码

用法：
    minutes = await config_service.get_int(db, "play.daily_max_minutes")
"""

import json
import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_entry import ConfigEntry

logger = logging.getLogger(__name__)

# 兜底默认值（类型随值推断：0/整数 / 0.0/浮点 / "" / True / 列表 / dict）
CONFIG_DEFAULTS: dict[str, Any] = {
    "play.daily_max_minutes": 0,  # 每日游戏时长上限（分钟，0 = 不限）
    "play.daily_max_games": 0,    # 每日对局上限（0 = 不限）
    "announcement.text": "",      # 公告文案（空 = 不展示；G2 运营下发）
    "app.min_client_ver": "",     # 最低客户端版本（H3 强更；小于该版本弹更新页）
    "app.latest_url": "",         # 强更跳转地址（应用商店 / 安装包 / 官网）
}

# 可下发给客户端的配置白名单（不进白名单的配置客户端永远看不到）
PUBLIC_CONFIG_KEYS: set[str] = {"announcement.text", "app.min_client_ver", "app.latest_url"}

# 读缓存：{key: (value, expire_ts)}，TTL 30s
_cache: dict[str, tuple[Any, float]] = {}
_CACHE_TTL = 30.0


def _invalidate(key: str) -> None:
    _cache.pop(key, None)


async def _load_raw(db: AsyncSession, key: str) -> str | None:
    row = await db.get(ConfigEntry, key)
    return row.value if row else None


async def _get_cached(db: AsyncSession, key: str) -> Any:
    """带 TTL 的读：默认值兜底 + JSON 解析"""
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and hit[1] > now:
        return hit[0]

    raw = await _load_raw(db, key)
    if raw is None:
        value = CONFIG_DEFAULTS.get(key)
    else:
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.error(f"[config] 配置值非法 JSON: {key}={raw[:200]}")
            value = CONFIG_DEFAULTS.get(key)
    _cache[key] = (value, now + _CACHE_TTL)
    return value


async def get(db: AsyncSession, key: str, default: Any = None) -> Any:
    value = await _get_cached(db, key)
    return default if value is None else value


async def get_int(db: AsyncSession, key: str) -> int:
    return int(await _get_cached(db, key) or 0)


async def set_config(db: AsyncSession, key: str, value: Any, remark: str = "") -> dict:
    """写入/更新配置（管理端调用）；写库后立即失效本地缓存"""
    row = await db.get(ConfigEntry, key)
    if row is None:
        row = ConfigEntry(cfg_key=key, value=json.dumps(value, ensure_ascii=False), remark=remark)
        db.add(row)
    else:
        row.value = json.dumps(value, ensure_ascii=False)
        if remark:
            row.remark = remark
    await db.commit()
    _invalidate(key)
    logger.info(f"[config] set {key} = {value!r}")
    return {key: value}


async def get_public(db: AsyncSession) -> dict:
    """客户端可见配置（仅白名单键；未写库用默认值）"""
    return {key: await get(db, key) for key in sorted(PUBLIC_CONFIG_KEYS)}


async def list_all(db: AsyncSession) -> list[dict]:
    stmt = select(ConfigEntry).order_by(ConfigEntry.cfg_key.asc())
    rows = (await db.execute(stmt)).scalars().all()
    result = []
    for row in rows:
        try:
            value = json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            value = row.value
        result.append({"key": row.cfg_key, "value": value, "remark": row.remark, "updated_at": row.updated_at})
    return result
