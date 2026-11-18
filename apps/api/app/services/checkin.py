"""Check-in (SRS 4.8). Authorization is per event: the organizer who owns it, or a user with
an active StaffAssignment (`app.deps.require_event_staff`). A platform role alone never
grants check-in.

**One admission per ticket, even with two devices.** A check-in is a single conditional
``UPDATE tickets SET status = 'checked_in' WHERE id = :id AND event_id = :event AND status =
'valid'``. Postgres row-locks the ticket, so when two scanners send the same ticket at once,
the second UPDATE waits for the first, re-reads the row, finds it no longer `valid` and
updates nothing. That request then reports `already_used`. `uq_checkin_active_ticket` (one
un-reversed check-in record per ticket) backs this up in the database.

**Status is always live.** The QR token only names the ticket (`app.tickets.tokens`), so a
ticket cancelled or refunded after it was emailed fails here.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import StaffAccess
from app.enums import CheckInMethod, EventStatus, StaffRole, TicketStatus
from app.errors import AppError
from app.models import (
    Attendee,
    CheckInRecord,
    Event,
    OrganizerProfile,
    StaffAssignment,
    Ticket,
    TicketType,
    User,
)
from app.schemas.checkin import (
    AttendeeSearchResult,
    CheckInEvent,
    CheckInStats,
    CheckInTicket,
    InvalidReason,
    ScanResult,
    UndoResult,
)
from app.services import audit
from app.tickets.tokens import ADMISSION_PREFIX, parse_admission_token

CAMPAIGN_PREFIX = "BFC1."
SEARCH_LIMIT = 50

_REJECTED: dict[TicketStatus, Literal["already_used", "cancelled", "refunded"]] = {
    TicketStatus.CHECKED_IN: "already_used",
    TicketStatus.CANCELLED: "cancelled",
    TicketStatus.REFUNDED: "refunded",
}

# Events stay in the scanner's list until a day after they end (late arrivals, undo).
_GRACE = timedelta(days=1)
_SCANNABLE = (EventStatus.PUBLISHED, EventStatus.UNPUBLISHED)


async def list_events(session: AsyncSession, user: User) -> list[CheckInEvent]:
    cutoff = datetime.now(UTC) - _GRACE
    owned = await session.scalars(
        select(Event)
        .join(OrganizerProfile, OrganizerProfile.id == Event.organizer_profile_id)
        .where(
            OrganizerProfile.user_id == user.id,
            Event.status.in_(_SCANNABLE),
            Event.ends_at > cutoff,
        )
    )
    assigned = (
        (
            await session.execute(
                select(Event, StaffAssignment.role)
                .join(StaffAssignment, StaffAssignment.event_id == Event.id)
                .where(
                    StaffAssignment.user_id == user.id,
                    StaffAssignment.revoked_at.is_(None),
                    Event.status.in_(_SCANNABLE),
                    Event.ends_at > cutoff,
                )
            )
        )
        .tuples()
        .all()
    )

    def item(event: Event, role: Literal["owner", "event_admin", "check_in_staff"]) -> CheckInEvent:
        return CheckInEvent(
            id=event.id,
            title=event.title,
            status=event.status,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            timezone=event.timezone,
            venue_name=event.venue.name if event.venue else None,
            role=role,
            can_undo=role != StaffRole.CHECK_IN_STAFF.value,
        )

    items = {e.id: item(e, "owner") for e in owned}
    for event, role in assigned:
        items.setdefault(
            event.id,
            item(event, "event_admin" if role is StaffRole.EVENT_ADMIN else "check_in_staff"),
        )
    return sorted(items.values(), key=lambda e: e.starts_at)


# --- scanning ---------------------------------------------------------------------------


def _invalid_reason(payload: str) -> InvalidReason:
    # A Campaign QR holds `BFC1.<token>` or a link to `/c/BFC1.<token>`. Say so explicitly,
    # so door staff can tell the attendee they showed a promotion, not a ticket.
    if CAMPAIGN_PREFIX in payload and not payload.strip().startswith(ADMISSION_PREFIX):
        return "campaign_qr_not_admission"
    return "unrecognized"


async def stats(session: AsyncSession, event_id: uuid.UUID) -> CheckInStats:
    rows = (
        await session.execute(
            select(Ticket.status, func.count())
            .where(
                Ticket.event_id == event_id,
                Ticket.status.in_((TicketStatus.VALID, TicketStatus.CHECKED_IN)),
            )
            .group_by(Ticket.status)
        )
    ).tuples()
    counts = dict(rows.all())
    checked_in = counts.get(TicketStatus.CHECKED_IN, 0)
    return CheckInStats(
        registered=checked_in + counts.get(TicketStatus.VALID, 0), checked_in=checked_in
    )


async def _ticket_view(session: AsyncSession, ticket_id: uuid.UUID) -> CheckInTicket | None:
    row = (
        await session.execute(
            select(Ticket, Attendee.full_name, TicketType.name)
            .join(Attendee, Attendee.id == Ticket.attendee_id)
            .join(TicketType, TicketType.id == Ticket.ticket_type_id)
            .where(Ticket.id == ticket_id)
            .execution_options(populate_existing=True)
        )
    ).first()
    if row is None:
        return None
    ticket, attendee_name, type_name = row
    return _to_view(ticket, attendee_name, type_name)


def _to_view(ticket: Ticket, attendee_name: str, type_name: str) -> CheckInTicket:
    return CheckInTicket(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        status=ticket.status,
        attendee_name=attendee_name,
        ticket_type_name=type_name,
        checked_in_at=ticket.checked_in_at,
    )


async def _check_in(
    session: AsyncSession,
    access: StaffAccess,
    ticket_id: uuid.UUID,
    method: CheckInMethod,
    device_label: str | None,
) -> ScanResult:
    event_id = access.event.id
    now = datetime.now(UTC)
    admitted = await session.scalar(
        update(Ticket)
        .where(
            Ticket.id == ticket_id,
            Ticket.event_id == event_id,
            Ticket.status == TicketStatus.VALID,
        )
        .values(status=TicketStatus.CHECKED_IN, checked_in_at=now)
        .returning(Ticket.id)
    )
    if admitted is not None:
        session.add(
            CheckInRecord(
                ticket_id=ticket_id,
                event_id=event_id,
                checked_in_by_user_id=access.user.id,
                method=method,
                checked_in_at=now,
                device_label=device_label,
            )
        )
        view = await _ticket_view(session, ticket_id)
        assert view is not None
        audit.record(
            session,
            actor_id=access.user.id,
            action="ticket.checked_in",
            entity_type="ticket",
            entity_id=ticket_id,
            description=(
                f"Checked in {view.ticket_number} ({view.attendee_name}) by {method.value}."
            ),
            event_id=event_id,
        )
        await session.commit()
        return ScanResult(
            result="valid", ticket=view, method=method, stats=await stats(session, event_id)
        )

    # Nothing was updated: the ticket isn't this event's, or it isn't `valid` any more.
    view = await _ticket_view(session, ticket_id)
    ticket_event = await session.scalar(select(Ticket.event_id).where(Ticket.id == ticket_id))
    if view is None or ticket_event != event_id:
        # Don't describe another event's ticket to this event's staff.
        reason: InvalidReason = "unrecognized" if view is None else "wrong_event"
        return ScanResult(result="invalid", reason=reason, stats=await stats(session, event_id))
    if view.status is TicketStatus.VALID:
        # A concurrent undo made it valid again between our UPDATE and this read. Try once more.
        return await _check_in(session, access, ticket_id, method, device_label)
    outcome = _REJECTED[view.status]
    return ScanResult(result=outcome, ticket=view, stats=await stats(session, event_id))


async def scan(
    session: AsyncSession, access: StaffAccess, payload: str, device_label: str | None
) -> ScanResult:
    """SRS 4.8: validate authenticity, then live status, and record the check-in. Only
    `BFT1.` admission tokens can admit anyone; Campaign QR codes never do (SRS 4.14)."""
    ticket_id = parse_admission_token(payload)
    if ticket_id is None:
        return ScanResult(
            result="invalid",
            reason=_invalid_reason(payload),
            stats=await stats(session, access.event.id),
        )
    return await _check_in(session, access, ticket_id, CheckInMethod.QR_SCAN, device_label)


async def manual_check_in(
    session: AsyncSession, access: StaffAccess, ticket_id: uuid.UUID, device_label: str | None
) -> ScanResult:
    """SRS 4.8 "Search for attendees manually": the same atomic check-in, found by search
    instead of the camera."""
    return await _check_in(session, access, ticket_id, CheckInMethod.MANUAL_SEARCH, device_label)


async def undo(
    session: AsyncSession, access: StaffAccess, ticket_id: uuid.UUID, reason: str | None
) -> UndoResult:
    """SRS 4.8 "Undo an accidental check-in where authorized". The check-in record is kept
    and marked reversed, so the timeline shows both (SRS 4.16)."""
    if not access.can_undo:
        raise AppError(403, "checkin_undo_forbidden", "Check-in staff can't undo check-ins.")
    event_id = access.event.id
    record = await session.scalar(
        select(CheckInRecord)
        .where(
            CheckInRecord.ticket_id == ticket_id,
            CheckInRecord.event_id == event_id,
            CheckInRecord.reversed_at.is_(None),
        )
        .with_for_update()
    )
    if record is None:
        if await session.scalar(
            select(Ticket.id).where(Ticket.id == ticket_id, Ticket.event_id == event_id)
        ):
            raise AppError(409, "not_checked_in", "This ticket isn't checked in.")
        raise AppError(404, "ticket_not_found", "Ticket not found.")
    now = datetime.now(UTC)
    record.reversed_at = now
    record.reversed_by_user_id = access.user.id
    record.reversal_reason = reason
    # Only a checked-in ticket goes back to valid. If it was refunded or cancelled since,
    # it stays that way; the reversal is still recorded.
    await session.execute(
        update(Ticket)
        .where(Ticket.id == ticket_id, Ticket.status == TicketStatus.CHECKED_IN)
        .values(status=TicketStatus.VALID, checked_in_at=None)
    )
    view = await _ticket_view(session, ticket_id)
    assert view is not None
    audit.record(
        session,
        actor_id=access.user.id,
        action="ticket.check_in_reversed",
        entity_type="ticket",
        entity_id=ticket_id,
        description=f"Reversed the check-in of {view.ticket_number} ({view.attendee_name})."
        + (f" Reason: {reason}" if reason else ""),
        event_id=event_id,
    )
    await session.commit()
    return UndoResult(ticket=view, stats=await stats(session, event_id))


# --- search -----------------------------------------------------------------------------


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def search_tickets(
    session: AsyncSession,
    event_id: uuid.UUID,
    q: str | None,
    status: TicketStatus | None = None,
    limit: int = SEARCH_LIMIT,
) -> list[CheckInTicket]:
    """Tickets of one event, matched on attendee name, attendee email or ticket number
    (case-insensitive). Shared by the scanner's manual search and the organizer's
    attendee list."""
    query = (
        select(Ticket, Attendee.full_name, TicketType.name)
        .join(Attendee, Attendee.id == Ticket.attendee_id)
        .join(TicketType, TicketType.id == Ticket.ticket_type_id)
        .where(Ticket.event_id == event_id)
    )
    term = (q or "").strip()
    if term:
        pattern = _like(term)
        query = query.where(
            or_(
                Attendee.full_name.ilike(pattern, escape="\\"),
                Attendee.email.ilike(pattern, escape="\\"),
                Ticket.ticket_number.ilike(pattern, escape="\\"),
            )
        )
    if status is not None:
        query = query.where(Ticket.status == status)
    rows = (
        await session.execute(query.order_by(Attendee.full_name, Ticket.ticket_number).limit(limit))
    ).tuples()
    return [_to_view(t, name, type_name) for t, name, type_name in rows]


async def search(session: AsyncSession, access: StaffAccess, q: str | None) -> AttendeeSearchResult:
    return AttendeeSearchResult(
        tickets=await search_tickets(session, access.event.id, q),
        stats=await stats(session, access.event.id),
    )
