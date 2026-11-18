"""Staff assignments (SRS 4.8): organizers authorize existing users to check in at one event."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import StaffRole
from app.errors import AppError
from app.models import Event, OrganizerProfile, StaffAssignment, User
from app.schemas.staff import StaffAssign, StaffRead
from app.services import audit
from app.services.auth import get_user_by_email


async def list_staff(session: AsyncSession, event: Event) -> list[StaffRead]:
    rows = (
        (
            await session.execute(
                select(StaffAssignment, User)
                .join(User, User.id == StaffAssignment.user_id)
                .where(StaffAssignment.event_id == event.id, StaffAssignment.revoked_at.is_(None))
                .order_by(StaffAssignment.created_at)
            )
        )
        .tuples()
        .all()
    )
    return [
        StaffRead(
            id=a.id,
            user_id=u.id,
            full_name=u.full_name,
            email=u.email,
            role=a.role,
            assigned_at=a.created_at,
        )
        for a, u in rows
    ]


async def assign(
    session: AsyncSession, event: Event, organizer: User, data: StaffAssign
) -> StaffRead:
    user = await get_user_by_email(session, data.email)
    if user is None or user.is_suspended:
        # Organizer-facing, so naming the problem is fine; the person must register first.
        raise AppError(
            404,
            "user_not_found",
            "No active BiletFlow account uses that email. Ask them to register first.",
        )
    owner_id = await session.scalar(
        select(OrganizerProfile.user_id).where(OrganizerProfile.id == event.organizer_profile_id)
    )
    if user.id == owner_id:
        raise AppError(409, "already_owner", "You already manage this event.")
    assignment = StaffAssignment(
        id=uuid.uuid4(),
        event_id=event.id,
        user_id=user.id,
        role=StaffRole(data.role),
        assigned_by_user_id=organizer.id,
    )
    try:
        async with session.begin_nested():
            session.add(assignment)
            await session.flush()
    except IntegrityError as exc:  # uq_staff_assignment_active
        raise AppError(
            409, "already_assigned", "This person is already on the event's staff."
        ) from exc
    audit.record(
        session,
        actor_id=organizer.id,
        action="staff.assigned",
        entity_type="staff_assignment",
        entity_id=assignment.id,
        description=f"Assigned {user.email} as {assignment.role.value.replace('_', ' ')}",
        event_id=event.id,
    )
    await session.commit()
    await session.refresh(assignment)
    return StaffRead(
        id=assignment.id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=assignment.role,
        assigned_at=assignment.created_at,
    )


async def revoke(
    session: AsyncSession, event: Event, organizer: User, assignment_id: uuid.UUID
) -> None:
    assignment = await session.scalar(
        select(StaffAssignment).where(
            StaffAssignment.id == assignment_id,
            StaffAssignment.event_id == event.id,
            StaffAssignment.revoked_at.is_(None),
        )
    )
    if assignment is None:
        raise AppError(404, "staff_not_found", "Staff assignment not found.")
    assignment.revoked_at = datetime.now(UTC)
    audit.record(
        session,
        actor_id=organizer.id,
        action="staff.revoked",
        entity_type="staff_assignment",
        entity_id=assignment.id,
        description="Removed a staff member from the event",
        event_id=event.id,
    )
    await session.commit()
