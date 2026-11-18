"""Authentication and permission dependencies.

Every check here derives identity and authority on the server: the user comes from a
verified access token and the database, never from a client-supplied id or role.

Event-scoped checks (`require_event_owner`, `require_event_staff`) live alongside the event
routes they protect and are added with them.
"""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.enums import UserRole
from app.errors import AppError
from app.models import User
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
    if user is None:
        raise unauthorized
    if user.is_suspended:
        raise AppError(403, "account_suspended", "This account has been suspended.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


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
