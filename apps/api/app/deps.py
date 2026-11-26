"""Authentication and permission dependencies.

Every check here derives identity and authority on the server: the user comes from a
verified access token and the database, never from a client-supplied id or role.

Event-scoped checks return **404, not 403**, when the caller may not see the event, so an
outsider cannot tell a private event from one that does not exist.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.enums import StaffRole, UserRole
from app.errors import AppError
from app.models import Event, OrganizerProfile, StaffAssignment, User
from app.security import TokenType, decode_token

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False, description="Access token from /auth/login")


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    unauthorized = AppError(
        401, "unauthorized", "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    claims = decode_token(credentials.credentials, TokenType.ACCESS)
    user = await session.get(User, uuid.UUID(claims["sub"]))
    # A deleted account's access tokens stop working at once, not when they expire.
    if user is None or user.deleted_at is not None:
        raise unauthorized
    if user.is_suspended:
        raise AppError(403, "account_suspended", "This account has been suspended.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User | None:
    """The signed-in user if there is a valid token, else None. For public pages that show
    a little more to the right person (e.g. a private event to its staff)."""
    if credentials is None:
        return None
    try:
        return await get_current_user(session, credentials)
    except AppError:
        return None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_role(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    """Dependency factory: the signed-in user must hold one of these platform roles.

    Platform role only. Being an Event Admin for one event is a StaffAssignment, checked by
    `require_event_staff`, not a value of `User.role`.
    """
    allowed = frozenset(roles)

    async def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise AppError(403, "forbidden", "Your account cannot do this.")
        return user

    return dependency


OrganizerUser = Annotated[User, Depends(require_role(UserRole.ORGANIZER))]
PlatformAdminUser = Annotated[User, Depends(require_role(UserRole.PLATFORM_ADMIN))]


async def get_organizer_profile(session: SessionDep, user: OrganizerUser) -> OrganizerProfile:
    # Imported here to keep deps free of a module-level dependency on the services layer.
    from app.services.organizer import get_or_create_profile

    return await get_or_create_profile(session, user)


CurrentOrganizer = Annotated[OrganizerProfile, Depends(get_organizer_profile)]


async def get_owned_event(
    event_id: uuid.UUID, session: SessionDep, organizer: CurrentOrganizer
) -> Event:
    """The event, if the signed-in organizer owns it. Ownership comes from the database,
    never from the request."""
    event = await session.scalar(
        select(Event).where(Event.id == event_id, Event.organizer_profile_id == organizer.id)
    )
    if event is None:
        raise AppError(404, "event_not_found", "Event not found.")
    return event


OwnedEvent = Annotated[Event, Depends(get_owned_event)]


@dataclass(frozen=True)
class StaffAccess:
    """Why the signed-in user may work an event's door (SRS 4.8)."""

    event: Event
    user: User
    role: Literal["owner", "event_admin", "check_in_staff"]

    @property
    def can_undo(self) -> bool:
        """SRS 4.8 "Undo an accidental check-in where authorized": owners and event admins.
        Check-in staff scan only."""
        return self.role != "check_in_staff"


async def require_event_staff(
    event_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> StaffAccess:
    """The event's owner, or a user with an active StaffAssignment for it. A platform role
    alone grants nothing here. Anyone else gets 404, so they can't probe which events exist.
    """
    event = await session.get(Event, event_id)
    if event is not None:
        owner_user_id = await session.scalar(
            select(OrganizerProfile.user_id).where(
                OrganizerProfile.id == event.organizer_profile_id
            )
        )
        if owner_user_id == user.id:
            return StaffAccess(event=event, user=user, role="owner")
        role = await session.scalar(
            select(StaffAssignment.role).where(
                StaffAssignment.event_id == event.id,
                StaffAssignment.user_id == user.id,
                StaffAssignment.revoked_at.is_(None),
            )
        )
        if role is not None:
            return StaffAccess(
                event=event,
                user=user,
                role="event_admin" if role is StaffRole.EVENT_ADMIN else "check_in_staff",
            )
    raise AppError(404, "event_not_found", "Event not found.")


EventStaff = Annotated[StaffAccess, Depends(require_event_staff)]
