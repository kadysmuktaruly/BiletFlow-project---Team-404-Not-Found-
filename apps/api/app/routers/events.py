"""/events: the public side of events (SRS 4.2). No sign-in needed."""

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.config import get_settings
from app.deps import CurrentUser, OptionalUser, SessionDep
from app.errors import error_responses
from app.i18n import Locale
from app.schemas.admin import ReportCreate, ReportCreated
from app.schemas.event import PublicEventList, PublicEventRead
from app.services import admin as admin_service
from app.services import calendar as calendar_service
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


@router.get(
    "/{slug}/calendar.ics",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {}}}, **error_responses(404)},
    summary="Add the event to a calendar (.ics)",
    description=(
        "An iCalendar file for any event you can open by slug (same rules as the event "
        "page). Times are in the event's IANA time zone, so calendars show its local time. "
        "`lang` picks the language of the event link inside it."
    ),
)
async def event_calendar(
    slug: str, session: SessionDep, user: OptionalUser, lang: Locale = "kk"
) -> Response:
    event = await event_service.get_public_by_slug(session, slug, user)
    base = get_settings().public_base_url.rstrip("/")
    ics = calendar_service.event_ics(event, f"{base}/{lang}/events/{event.slug}")
    return Response(
        ics,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{event.slug}.ics"'},
    )


@router.post(
    "/{slug}/report",
    response_model=ReportCreated,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 404, 409, 422),
    summary="Report an event to the platform",
    description=(
        "Signed-in users report an event they can see (fraud, misleading, inappropriate, "
        "spam, other). A Platform Admin reviews it. One open report per person per event "
        "(`409 report_already_open`)."
    ),
)
async def report_event(
    slug: str, data: ReportCreate, user: CurrentUser, session: SessionDep
) -> ReportCreated:
    report = await admin_service.report_event(session, user, slug, data)
    return ReportCreated(id=report.id, status=report.status)
