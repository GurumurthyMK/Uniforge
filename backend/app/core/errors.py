"""Shared error-handling conventions.

Envelope for errors (used by handlers and documented for clients):

    {"error": {"code": "<MACHINE_CODE>", "message": "<human message>", "details": {...} | null}}

Conventions:
- Validate all external input with Pydantic (422 handled below).
- Domain errors should raise AppError subclasses; handlers convert them.
- Never trust client-side authorization; handlers never leak internals.
"""

from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    details: Optional[dict[str, Any]] = None


def error_payload(code: str, message: str, details: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(code, str(exc.detail), None),
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_payload(
            "VALIDATION_ERROR", "Request validation failed.", {"errors": _json_safe_errors(exc.errors())}
        ),
    )


def _json_safe_errors(errors: list[dict]) -> list[dict]:
    """Pydantic v2 embeds raw exception objects in error `ctx`; coerce them
    to strings so the envelope stays JSON-serializable."""

    def _safe(value: object) -> object:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [_safe(v) for v in value]
        if isinstance(value, dict):
            return {str(k): _safe(v) for k, v in value.items()}
        if isinstance(value, tuple):
            return [_safe(v) for v in value]
        return str(value)

    return [{**e, "ctx": _safe(e.get("ctx"))} if "ctx" in e else e for e in errors]


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_payload("INTERNAL_ERROR", "An unexpected error occurred.", None),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
