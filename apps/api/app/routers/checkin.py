"""/checkin: endpoints for the Event Admin scanner app (SRS 4.8).

Every event-scoped endpoint requires the event's owner or an active staff assignment
(`EventStaff`). Anyone else gets 404.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import CurrentUser, EventStaff, SessionDep
from app.errors import error_responses
from app.schemas.checkin import (
    AttendeeSearchResult,
    CheckInEvent,
    CheckInStats,
    ManualCheckInRequest,
    ScanRequest,
    ScanResult,
    UndoCheckInRequest,
    UndoResult,
)
from app.services import checkin as checkin_service

router = APIRouter(prefix="/checkin", tags=["check-in"], responses=error_responses(401, 403))


@router.get(
    "/events",
    response_model=list[CheckInEvent],
    summary="Events you can check attendees in at",
    description=(
        "Only events you organize or are assigned to as staff (SRS 4.8: 'view only assigned "
        "events'), while published or unpublished and until a day after they end."
    ),
)
async def list_events(user: CurrentUser, session: SessionDep) -> list[CheckInEvent]:
    return await checkin_service.list_events(session, user)


@router.post(
    "/events/{event_id}/scan",
    response_model=ScanResult,
    responses=error_responses(404, 422),
    summary="Validate a scanned QR code and check the ticket in",
    description=(
        "Send the raw QR text. The result is always 200 with one of `valid`, `invalid`, "
        "`cancelled`, `refunded` or `already_used`. `valid` means this request recorded the "
        "check-in: if two devices scan one ticket at once, exactly one gets `valid` and the "
        "other `already_used`. Campaign QR codes are always `invalid` with reason "
        "`campaign_qr_not_admission`. Includes live registered and checked-in counts."
    ),
)
async def scan(data: ScanRequest, access: EventStaff, session: SessionDep) -> ScanResult:
    return await checkin_service.scan(session, access, data.payload, data.device_label)


@router.post(
    "/events/{event_id}/tickets/{ticket_id}/check-in",
    response_model=ScanResult,
    responses=error_responses(404, 422),
    summary="Check a ticket in from manual search",
    description="The same atomic check-in and results as a scan, for a ticket found by search.",
)
async def manual_check_in(
    ticket_id: uuid.UUID,
    access: EventStaff,
    session: SessionDep,
    data: ManualCheckInRequest | None = None,
) -> ScanResult:
    return await checkin_service.manual_check_in(
        session, access, ticket_id, data.device_label if data else None
    )


@router.post(
    "/events/{event_id}/tickets/{ticket_id}/undo",
    response_model=UndoResult,
    responses=error_responses(404, 409, 422),
    summary="Undo an accidental check-in",
    description=(
        "Event owners and event admins only; check-in staff get "
        "`403 checkin_undo_forbidden`. The ticket becomes valid again, and the reversal is "
        "kept in the check-in history and the audit log. `409 not_checked_in` if there is "
        "nothing to undo."
    ),
)
async def undo(
    ticket_id: uuid.UUID,
    access: EventStaff,
    session: SessionDep,
    data: UndoCheckInRequest | None = None,
) -> UndoResult:
    return await checkin_service.undo(session, access, ticket_id, data.reason if data else None)


@router.get(
    "/events/{event_id}/stats",
    response_model=CheckInStats,
    responses=error_responses(404),
    summary="Registered and checked-in counts",
)
async def stats(access: EventStaff, session: SessionDep) -> CheckInStats:
    return await checkin_service.stats(session, access.event.id)


@router.get(
    "/events/{event_id}/attendees",
    response_model=AttendeeSearchResult,
    responses=error_responses(404, 422),
    summary="Search attendees for manual check-in",
    description=(
        "Matches attendee name, attendee email or ticket number, case-insensitively. "
        f"At most {checkin_service.SEARCH_LIMIT} results. Without `q`, lists the first ones."
    ),
)
async def search_attendees(
    access: EventStaff,
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> AttendeeSearchResult:
    return await checkin_service.search(session, access, q)
