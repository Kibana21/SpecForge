from typing import Any, Generic, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any = None


class Envelope(BaseModel, Generic[T]):
    data: T | None = None
    error: ErrorDetail | None = None
    meta: dict = {}


def ok(data: Any, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def err(code: str, message: str, status_code: int = 400, details: Any = None) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={"data": None, "error": {"code": code, "message": message, "details": details}, "meta": {}},
    )
