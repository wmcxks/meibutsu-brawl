"""远端关卡业务（D1）"""

import json
import logging
import time

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.level import Level

logger = logging.getLogger(__name__)

# 简单内存缓存（关卡配置低频变更；管理端更新后 30s 内生效）
_cache: dict[tuple, tuple[list[dict], float]] = {}
_CACHE_TTL = 30.0


def _parse_layout(row: Level) -> list | None:
    try:
        return json.loads(row.layout)
    except (json.JSONDecodeError, TypeError):
        logger.error(f"[level] 关卡 {row.level_id} 布局 JSON 非法")
        return None


def _to_dto(row: Level, layout: list) -> dict:
    return {
        "level_id": row.level_id,
        "title": row.title,
        "icon_types": row.icon_types,
        "regions": layout,
        "version": row.version,
    }


async def get_enabled_levels(db: AsyncSession) -> list[dict]:
    """启用的关卡列表（按 level_id 升序；含 30s 内存缓存）"""
    now = time.monotonic()
    hit = _cache.get("enabled")
    if hit and hit[1] > now:
        return hit[0]

    stmt = select(Level).where(Level.enabled.is_(True)).order_by(Level.level_id.asc())
    rows = (await db.execute(stmt)).scalars().all()
    items = []
    for row in rows:
        layout = _parse_layout(row)
        if layout is not None:
            items.append(_to_dto(row, layout))
    _cache[("enabled",)] = (items, now + _CACHE_TTL)
    return items


async def save_level(db: AsyncSession, level_id: int, title: str, icon_types: int, layout: list, remark: str = "") -> dict:
    """保存/更新关卡（管理端；校验 JSON 结构与最低字段）"""
    if not isinstance(layout, list) or len(layout) == 0:
        raise HTTPException(status_code=400, detail="布局不能为空")
    for region in layout:
        if not isinstance(region, dict) or "x" not in region or "y" not in region or "layers" not in region:
            raise HTTPException(status_code=400, detail="布局结构非法（需 RegionConfig[]）")
        if not isinstance(region["layers"], list) or len(region["layers"]) == 0:
            raise HTTPException(status_code=400, detail="布局缺少层定义")

    row = await db.get(Level, level_id)
    if row is None:
        row = Level(level_id=level_id, title=title, icon_types=icon_types, layout=json.dumps(layout, ensure_ascii=False), remark=remark, version=1)
        db.add(row)
    else:
        row.title = title
        row.icon_types = icon_types
        row.layout = json.dumps(layout, ensure_ascii=False)
        row.version = (row.version or 0) + 1
        if remark:
            row.remark = remark
    await db.commit()
    _cache.clear()
    logger.info(f"[level] saved level_id={level_id} v={row.version}")
    return _to_dto(row, layout)
