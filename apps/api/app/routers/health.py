"""Liveness plus a database round trip, for Docker health checks and uptime probes."""

import asyncio
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import AppError, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

# Well under the Compose health check's own timeout, so a hung database reports 503
# instead of the probe itself timing out.
_DB_TIMEOUT_SECONDS = 3.0


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse, "description": "Database unreachable"}},
)
async def health(session: Annotated[AsyncSession, Depends(get_session)]) -> HealthResponse:
    try:
        async with asyncio.timeout(_DB_TIMEOUT_SECONDS):
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Health check failed: database unreachable", exc_info=exc)
        raise AppError(503, "service_unavailable", "The database is unreachable.") from exc
    return HealthResponse(status="ok", database="ok")
