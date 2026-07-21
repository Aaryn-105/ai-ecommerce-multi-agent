"""FastAPI application factory with CORS, lifespan, and router registration."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.core.database import init_db
from backend.routers import chat, dashboard, report

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — runs startup and shutdown logic."""
    # ── Startup ──────────────────────────────────────────
    logger.info("Initializing database tables…")
    init_db()
    logger.info("Database ready.")

    yield

    # ── Shutdown ─────────────────────────────────────────
    logger.info("Shutting down…")


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    app = FastAPI(
        title="AI E-Commerce Multi-Agent System",
        description=(
            "Intelligent e-commerce product analysis platform powered by "
            "a multi-agent orchestration engine. Supports product selection, "
            "trend forecasting, competitor analysis, marketing copy generation, "
            "inventory advice, pricing, and promotion planning."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──────────────────────────────────────────
    app.include_router(chat.router)
    app.include_router(dashboard.router)
    app.include_router(report.router)

    # ── Health check ─────────────────────────────────────
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": "1.0.0"}

    return app


app = create_app()
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)