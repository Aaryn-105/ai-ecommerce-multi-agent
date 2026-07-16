"""SQLAlchemy engine, session factory, and base."""
from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.core.config import settings


# ── Engine ────────────────────────────────────────────────
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URL,
    echo=settings.DB_ECHO,
    connect_args={"check_same_thread": False}  # needed for SQLite
    if settings.SQLALCHEMY_DATABASE_URL.startswith("sqlite")
    else {},
)

# ── Session factory ───────────────────────────────────────
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ── Declarative base ─────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependency for FastAPI ───────────────────────────────
def get_db() -> Generator[Session, Any, None]:
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[Session, Any]:
    """Async-compatible DB dependency (synchronous session in threadpool)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables (development convenience)."""
    from backend.models.base import Base  # noqa: F811
    import backend.models.conversation  # noqa: F401  – register tables
    import backend.models.report  # noqa: F401

    Base.metadata.create_all(bind=engine)
