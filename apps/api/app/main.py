"""FastAPI application: routers under /api/v1, CORS, and the standard error shape.

Run locally from `apps/api`:  uv run uvicorn app.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import engine
from app.errors import ErrorResponse, install_error_handlers
from app.routers import activation, auth, events, health, me, orders, organizer
from app.services.orders import expiry_sweeper

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with expiry_sweeper(get_settings().order_sweep_interval_seconds):
        yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        # Every documented operation can fail with the standard error body.
        responses={422: {"model": ErrorResponse, "description": "Validation error"}},
    )

    # Credentials are allowed so the web app can send the refresh-token cookie, which is
    # also why origins must be listed exactly and never "*".
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Client"],
    )
    install_error_handlers(app)

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(me.router, prefix=API_PREFIX)
    app.include_router(organizer.router, prefix=API_PREFIX)
    app.include_router(events.router, prefix=API_PREFIX)
    app.include_router(orders.router, prefix=API_PREFIX)
    app.include_router(activation.router, prefix=API_PREFIX)
    return app


app = create_app()
