"""FastAPI dependency injection helpers."""
from __future__ import annotations

from typing import Any, Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.core.config import Settings, settings
from backend.core.database import get_db


def get_settings() -> Settings:
    """Provide the singleton Settings instance."""
    return settings


def get_db_session(
    db: Session = Depends(get_db),
) -> Generator[Session, Any, None]:
    """Alias for get_db – explicitly typed for route signatures."""
    yield db
