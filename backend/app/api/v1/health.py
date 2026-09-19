"""Health endpoints. No auth required. Used by local dev and AWS target groups."""

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str = "0.1.0"


class ReadyResponse(BaseModel):
    status: str
    database: str  # "up" | "down"


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="uniforge-api")


@router.get("/ready", response_model=ReadyResponse, summary="Readiness probe (includes DB)")
def ready(db: Session = Depends(get_db)) -> ReadyResponse:
    try:
        db.execute(text("SELECT 1"))
        return ReadyResponse(status="ok", database="up")
    except SQLAlchemyError:
        return ReadyResponse(status="degraded", database="down")
