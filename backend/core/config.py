"""Application configuration via pydantic-settings."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── OpenAI ──────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    LLM_MODEL_NAME: str = "deepseek-chat"
    LLM_API_BASE: str = "https://api.deepseek.com"

    # ── Database ────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./app.db"

    # ── FakeStore API ───────────────────────────────────
    FAKESTORE_API_BASE: str = "https://fakestoreapi.com"

    # ── Server ──────────────────────────────────────────
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_RELOAD: bool = True

    # ── Derived helpers ─────────────────────────────────
    @property
    def DB_ECHO(self) -> bool:
        return os.getenv("DEBUG", "").lower() in ("1", "true")

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        """Resolve SQLite path to project-root/data/."""
        url = self.DATABASE_URL
        if url.startswith("sqlite:///./"):
            rel = url.removeprefix("sqlite:///./")
            # backend/core/config.py → backend/core → backend → project root
            project_root = Path(__file__).resolve().parent.parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{data_dir / rel}"
        return url


settings = Settings()
