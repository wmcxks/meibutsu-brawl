"""管理后台 API（G1：最小可用的运营后台）

鉴权：X-Admin-Token 请求头 == 服务端 ADMIN_TOKEN（env 配置）。
未配置 ADMIN_TOKEN 时整个后台 403（默认关闭，避免裸奔上线）。
生产建议：ADMIN_TOKEN 用高强度随机串，并仅在内网/网关层暴露。
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.admin import AdminBanRequest, AdminCompensateRequest, AdminSetConfigRequest
from app.services import config_service, player_service, reward_service
from app.utils.response import success, error
from app.models.user import User
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/admin", tags=["管理后台"])


async def require_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")) -> None:
    if not settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="管理后台未启用（未配置 ADMIN_TOKEN）")
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="管理令牌无效")


@router.get("/users")
async def list_users(
    _: None = Depends(require_admin),
    keyword: str = Query(default="", description="按 openid / 昵称 模糊搜索"),
    status: int | None = Query(default=None, ge=0, le=1, description="按账号状态过滤"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """用户列表（分页 + 关键字/状态过滤）"""
    from sqlalchemy import func as sa_func

    conditions = []
    if keyword:
        like = f"%{keyword}%"
        conditions.append(or_(User.openid.like(like), User.nickname.like(like)))
    if status is not None:
        conditions.append(User.status == status)

    total = (await db.execute(select(sa_func.count(User.id)).where(*conditions))).scalar_one()
    stmt = (
        select(User)
        .where(*conditions)
        .order_by(User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "id": u.id,
            "openid": u.openid,
            "nickname": u.nickname,
            "platform": u.platform,
            "region_code": u.region_code,
            "status": u.status,
            "login_count": u.login_count,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in rows
    ]
    return success(data={"total": total, "items": items})


@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: int,
    req: AdminBanRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """封禁 / 解封（status: 0 正常 / 1 封禁）"""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.status = req.status
    await db.commit()
    logger.warning(f"[admin] user_id={user_id} ban_status={req.status} reason={req.reason}")
    return success(data={"id": user.id, "status": user.status})


@router.post("/rewards/compensate")
async def compensate(
    req: AdminCompensateRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """运营补偿道具（复用 C1 发放逻辑；跳过渠道上限、仍需 nonce 幂等）"""
    try:
        await player_service.assert_user_active(db, req.user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

    data = await reward_service.grant_prop(
        db, req.user_id, "op:compensation", req.prop_key, req.amount,
        nonce=req.nonce or None,
    )
    logger.info(f"[admin] compensate user_id={req.user_id} prop={req.prop_key} +{req.amount} remark={req.remark}")
    return success(data=data)


@router.get("/configs")
async def list_configs(_: None = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """查看全部远端配置"""
    items = await config_service.list_all(db)
    return success(data={"items": items})


@router.put("/configs/{cfg_key}")
async def set_config(
    cfg_key: str,
    req: AdminSetConfigRequest,
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """写入/热更新远端配置（如 play.daily_max_minutes=30 立即生效）"""
    data = await config_service.set_config(db, cfg_key, req.value, remark=req.remark)
    return success(data=data)


@router.get("/stats/overview")
async def stats_overview(
    _: None = Depends(require_admin),
    days: int = Query(default=7, ge=1, le=30, description="近 N 天序列长度"),
    db: AsyncSession = Depends(get_db),
):
    """运营指标概览（F2）：总量 + 近 N 天序列（活跃/新增/对局/时长/通关）

    口径说明：
      - 活跃 = 当天有任意对局/奖励结算的用户（hd_player_daily 有行）
      - 新增 = 当天注册的用户数（按数据库本地日，粗口径）
    """
    from datetime import date, datetime, timedelta, timezone
    from sqlalchemy import func as sa_func
    from app.models.player_daily import PlayerDaily
    from app.models.record import Record
    from app.models.user import User

    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)

    users_total = (await db.execute(select(sa_func.count(User.id)))).scalar_one()
    records_total = (await db.execute(select(sa_func.count(Record.id)))).scalar_one()

    # 近 N 天序列（按活跃日分组聚合）
    daily_rows = (
        await db.execute(
            select(
                PlayerDaily.stat_date,
                sa_func.count(sa_func.distinct(PlayerDaily.user_id)).label("active"),
                sa_func.coalesce(sa_func.sum(PlayerDaily.games), 0).label("games"),
                sa_func.coalesce(sa_func.sum(PlayerDaily.wins), 0).label("wins"),
                sa_func.coalesce(sa_func.sum(PlayerDaily.play_seconds), 0.0).label("seconds"),
            )
            .where(PlayerDaily.stat_date >= start)
            .group_by(PlayerDaily.stat_date)
            .order_by(PlayerDaily.stat_date.asc())
        )
    ).all()

    # 近 N 天新增（按 created_at 的本地日期粗口径）
    new_rows = (
        await db.execute(
            select(
                sa_func.date(User.created_at).label("d"),
                sa_func.count(User.id).label("n"),
            )
            .where(User.created_at >= datetime.combine(start, datetime.min.time()))
            .group_by(sa_func.date(User.created_at))
        )
    ).all()
    new_by_day = {row.d: row.n for row in new_rows}

    series = []
    for offset in range(days):
        d = start + timedelta(days=offset)
        row = next((r for r in daily_rows if r.stat_date == d), None)
        series.append(
            {
                "date": d.isoformat(),
                "active": int(row.active) if row else 0,
                "new": int(new_by_day.get(d, 0)),
                "games": int(row.games) if row else 0,
                "wins": int(row.wins) if row else 0,
                "play_seconds": round(float(row.seconds), 1) if row else 0.0,
            }
        )

    return success(
        data={
            "users_total": int(users_total),
            "records_total": int(records_total),
            "today": series[-1] if series else None,
            "series": series,
        }
    )
