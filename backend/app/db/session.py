"""Database engine/session configuration.

- Engine is created lazily from Settings.database_url.
- get_db() is a FastAPI dependency yielding a session per request.
- check_connection() is used by the health endpoint with a short timeout
  so /health stays fast even when Postgres is unreachable.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_timeout=5,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def check_connection(timeout_seconds: int = 2) -> bool:
    """Return True if a trivial SELECT succeeds, else False. Never raises."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn = conn.execution_options(timeout=timeout_seconds)
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
    except Exception:
        return False
