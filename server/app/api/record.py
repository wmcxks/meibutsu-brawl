"""通关记录 API 路由"""

import hashlib
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.schemas.record import RecordStartRequest, RecordSubmit
from app.services import anti_cheat_service, record_service
from app.utils.response import success, error
from config import get_settings

router = APIRouter(prefix="/api/record", tags=["通关记录"])

settings = get_settings()
SALT = settings.ANTI_CHEAT_SALT
SKEW_SECONDS = settings.ANTI_CHEAT_SKEW_SECONDS


def _fmt_clear_time(value: float) -> str:
    """格式化 clear_time，与前端 JS 的 String(score) 完全一致：
    整数不带小数点（12 → "12"），小数走最短表示（12.5 → "12.5"）。
    """
    return str(int(value)) if value == int(value) else f"{value}"


def verify_sign(req: RecordSubmit) -> None:
    """防刷校验：防重放 + 签名验证，放在业务逻辑最前端

    签名规则（与前端完全一致，Web Crypto / hashlib 均用原生 SHA-256）：
        sha256(f"{level_id}{clear_time}{timestamp}{SALT}") == sign
    时间戳误差超过 60 秒抛 400（请求过期），签名不符抛 403（签名校验失败）。
    """
    # 1. 防重放：时间戳误差超过 SKEW_SECONDS 视为过期请求
    now = int(time.time())
    if abs(now - req.timestamp) > SKEW_SECONDS:
        raise HTTPException(status_code=400, detail="请求过期")

    # 2. 签名校验：防止篡改 level_id / clear_time
    raw = f"{req.level_id}{_fmt_clear_time(req.clear_time)}{req.timestamp}{SALT}"
    expect = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if expect != req.sign:
        raise HTTPException(status_code=403, detail="签名校验失败")


@router.post("/start")
async def start_record(
    req: RecordStartRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """开局：生成结算会话，作为防机刷的时序基准"""
    try:
        session_id = await anti_cheat_service.start_session(req.level_id)
        return success(data={"session_id": session_id})
    except Exception as e:
        return error(message=str(e))


@router.post("/submit")
async def submit_record(
    req: RecordSubmit,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """提交通关记录（签名 + 会话 + 时序 + 限频，防机刷）"""
    # 1. 签名与时间戳防重放
    verify_sign(req)

    # 2. 限频：同一用户每分钟最多结算 3 次
    await anti_cheat_service.enforce_submit_rate_limit(user_id)

    # 3. 会话校验：session_id 存在且 level_id 匹配（防张冠李戴）
    session = await anti_cheat_service.get_session(req.session_id)
    if session["level_id"] != req.level_id:
        await anti_cheat_service.log_cheat(
            db, user_id, req.session_id, req.level_id,
            reason="level_mismatch",
            detail=f"session_level={session['level_id']}",
        )
        raise HTTPException(status_code=403, detail="关卡与开局会话不匹配")

    # 4. 时序校验：clear_time 必须在理论时间内且不低于最短通关时间
    elapsed = time.time() - session["start_time"]
    if req.clear_time > elapsed + settings.CLEAR_TIME_TOLERANCE_SECONDS:
        await anti_cheat_service.log_cheat(
            db, user_id, req.session_id, req.level_id,
            reason="impossible_time",
            detail=f"clear_time={req.clear_time:.3f} elapsed={elapsed:.3f}",
        )
        raise HTTPException(status_code=403, detail="成绩时间异常")
    if req.clear_time < settings.MIN_CLEAR_TIME_SECONDS:
        await anti_cheat_service.log_cheat(
            db, user_id, req.session_id, req.level_id,
            reason="too_fast",
            detail=f"clear_time={req.clear_time:.3f}",
        )
        raise HTTPException(status_code=403, detail="成绩时间异常")

    # 5. 落库（原有逻辑不变）
    try:
        record = await record_service.submit_record(user_id, req.level_id, req.clear_time, db)
    except Exception as e:
        return error(message=str(e))

    # 6. 结算成功：删除会话，防止重放
    await anti_cheat_service.delete_session(req.session_id)

    return success(data={"id": record.id})


@router.get("/list")
async def get_records(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的通关记录"""
    try:
        records = await record_service.get_records(user_id, db)
        return success(data=records)
    except Exception as e:
        return error(message=str(e))


@router.get("/rank")
async def get_rank(
    level_id: int = Query(default=1, description="关卡ID"),
    limit: int = Query(default=50, le=100, description="返回数量"),
    db: AsyncSession = Depends(get_db),
):
    """获取指定关卡的通关排行榜（无需登录）"""
    try:
        rank = await record_service.get_rank(level_id, limit, db)
        return success(data=rank)
    except Exception as e:
        return error(message=str(e))
