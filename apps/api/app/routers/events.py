"""/events: the public side of events (SRS 4.2). No sign-in needed."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import OptionalUser, SessionDep
from app.errors import error_responses
from app.schemas.event import PublicEventList, PublicEventRead
from app.services import events as event_service

router = APIRouter(prefix="/events", tags=["events"])


@router.get(
    "",
    response_model=PublicEventList,
    summary="Upcoming public events",
    description="Only published, public, upcoming events. Unlisted and private ones never appear.",
)
async def list_events(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=100, description="Search title or category")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PublicEventList:
    return await event_service.list_public(session, q=q, limit=limit, offset=offset)


@router.get(
    "/{slug}",
    response_model=PublicEventRead,
    responses=error_responses(404),
    summary="An event's public page",
    description=(
        "Public and unlisted events open by slug. Private events open only for their "
        "organizer and staff (send the access token); everyone else gets 404."
    ),
)
async def read_event(slug: str, session: SessionDep, user: OptionalUser) -> PublicEventRead:
    event = await event_service.get_public_by_slug(session, slug, user)
    return await event_service.public_read(session, event)
