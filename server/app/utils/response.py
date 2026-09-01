"""统一响应格式"""

from typing import Any
from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一 API 响应结构"""
    code: int = 0
    message: str = "ok"
    data: Any = None


def success(data: Any = None, message: str = "ok") -> dict:
    """成功响应"""
    return {"code": 0, "message": message, "data": data}


def error(message: str = "error", code: int = -1) -> dict:
    """失败响应"""
    return {"code": code, "message": message, "data": None}
