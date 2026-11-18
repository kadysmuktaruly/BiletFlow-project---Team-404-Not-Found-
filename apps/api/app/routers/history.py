"""/history: an event's activity timeline (SRS 4.16), for its organizer, event admins and
Platform Admins. Anyone else gets 404."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import CurrentUser, SessionDep
from app.errors import error_responses
from app.schemas.history import Timeline
from app.services import history as history_service

router = APIRouter(prefix="/history", tags=["history"], responses=error_responses(401))


@router.get(
    "/events/{event_id}/timeline",
    response_model=Timeline,
    responses=error_responses(404, 422),
    summary="An event's activity timeline, newest first",
    description=(
        "From the append-only audit log: publication and cancellation, price and capacity "
        "changes, refunds, promo codes, support-case changes, check-ins and reversals, and "
        "more. Filter by date range (event time zone) and by `category` (the part of the "
        "action before the dot, e.g. `order`, `promo`, `ticket`). Up to 500 entries."
    ),
)
async def event_timeline(
    event_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    date_from: date | None = None,
    date_to: date | None = None,
    category: Annotated[str | None, Query(max_length=40, pattern=r"^[a-z_]+$")] = None,
) -> Timeline:
    return await history_service.timeline(
        session, user, event_id, date_from=date_from, date_to=date_to, category=category
    )
