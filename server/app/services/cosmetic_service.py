"""装扮业务（C5：目录 / 拥有 / 购买(gem) / 装备）

- 免费默认款（price_gem=0）视为人人拥有，不落 hd_user_cosmetics
- 购买 = 钱包账本 debit(gem, event_id=cosmetic:{item_key}) 幂等 + 落拥有
- 装备 = 同 kind 其他装备位清零后置 1（单事务）
"""

import json
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cosmetic import Cosmetic, UserCosmetic
from app.services import wallet_service

logger = logging.getLogger(__name__)


async def _load_meta(db: AsyncSession, item_key: str) -> Cosmetic:
    meta = await db.get(Cosmetic, item_key)
    if meta is None:
        raise HTTPException(status_code=404, detail="装扮不存在")
    if not meta.enabled:
        raise HTTPException(status_code=404, detail="装扮已下架")
    return meta


def _catalog_item(meta: Cosmetic, owned: bool, equipped: bool) -> dict:
    try:
        extra = json.loads(meta.extra) if meta.extra else {}
    except (json.JSONDecodeError, TypeError):
        extra = {}
    return {
        "item_key": meta.item_key,
        "kind": meta.kind,
        "name": meta.name,
        "price_gem": meta.price_gem,
        "owned": owned,
        "equipped": equipped,
    }


async def list_catalog(db: AsyncSession, user_id: int | None = None) -> dict:
    """商店目录（无需登录可看；带 user_id 时合并拥有/装备态）"""
    metas = (
        await db.execute(
            select(Cosmetic)
            .where(Cosmetic.enabled.is_(True))
            .order_by(Cosmetic.sort_order.asc(), Cosmetic.item_key.asc())
        )
    ).scalars().all()

    owned_keys: set[str] = set()
    equipped_keys: set[str] = set()
    if user_id is not None:
        rows = (
            await db.execute(select(UserCosmetic).where(UserCosmetic.user_id == user_id))
        ).scalars().all()
        for r in rows:
            owned_keys.add(r.item_key)
            if r.equipped:
                equipped_keys.add(r.item_key)

    items = [
        _catalog_item(m, m.item_key in owned_keys or m.price_gem == 0, m.item_key in equipped_keys)
        for m in metas
    ]
    return {"items": items}


async def mine(db: AsyncSession, user_id: int) -> dict:
    """我的装扮（含免费默认款；equipped 每 kind 一个）"""
    data = await list_catalog(db, user_id)
    items = [it for it in data["items"] if it["owned"]]
    return {"items": items}


async def _clear_same_kind_equipped(db: AsyncSession, user_id: int, meta: Cosmetic) -> None:
    """把同 kind 其他商品的装备位清零（免费款无行也兼容）"""
    same_kind_keys = select(Cosmetic.item_key).where(Cosmetic.kind == meta.kind)
    await db.execute(
        UserCosmetic.__table__.update()
        .where(UserCosmetic.user_id == user_id, UserCosmetic.item_key.in_(same_kind_keys))
        .values(equipped=0)
    )


async def buy(db: AsyncSession, user_id: int, item_key: str) -> dict:
    """购买装扮（gem 账本扣款幂等；买即装备，同 kind 自动替换）"""
    meta = await _load_meta(db, item_key)
    if meta.price_gem <= 0:
        raise HTTPException(status_code=400, detail="免费默认款无需购买")

    # 已拥有 → 幂等返回当前装备态
    exists = await db.get(UserCosmetic, (user_id, item_key))
    if exists is not None:
        return {"item_key": item_key, "owned": True, "equipped": bool(exists.equipped), "already": True}

    # 扣款（event_id 幂等；余额不足抛 400）
    await wallet_service.debit(
        db, user_id, "gem", meta.price_gem,
        event_type="purchase", event_id=f"cosmetic:{item_key}", detail=item_key,
    )

    # 落拥有并装备（先清同 kind 其他装备位）
    await _clear_same_kind_equipped(db, user_id, meta)
    db.add(UserCosmetic(user_id=user_id, item_key=item_key, equipped=1))
    await db.commit()

    logger.info(f"[cosmetic] user_id={user_id} buy {item_key} (-{meta.price_gem} gem)")
    return {"item_key": item_key, "owned": True, "equipped": True, "already": False}


async def equip(db: AsyncSession, user_id: int, item_key: str) -> dict:
    """装备已拥有装扮（免费款/已购均可）"""
    meta = await _load_meta(db, item_key)
    owned = meta.price_gem == 0 or (await db.get(UserCosmetic, (user_id, item_key))) is not None
    if not owned:
        raise HTTPException(status_code=403, detail="尚未拥有该装扮")

    await _clear_same_kind_equipped(db, user_id, meta)
    # 免费款无行 → upsert 装备位（同键冲突忽略）
    row = await db.get(UserCosmetic, (user_id, item_key))
    if row is None:
        db.add(UserCosmetic(user_id=user_id, item_key=item_key, equipped=1))
    else:
        row.equipped = 1
    await db.commit()

    logger.info(f"[cosmetic] user_id={user_id} equip {item_key}")
    return {"item_key": item_key, "equipped": True}
