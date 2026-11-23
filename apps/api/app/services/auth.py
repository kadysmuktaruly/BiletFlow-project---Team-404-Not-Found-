"""Accounts and sessions (SRS 4.1).

Two rules shape this module:

* **No email enumeration, except at registration.** Resend-verification and
  forgot-password behave the same, and take about as long, whether or not the email is
  registered. Login gives one error for an unknown email and a wrong password, and still
  runs a full Argon2 check against a dummy hash when the email is unknown. Registration
  is the exception (decided 2026-11-23): a taken email gets `email_taken`, because a
  silent "check your inbox" confused people who already had an account. The register
  rate limit slows anyone probing many emails.
* **The server decides the role.** Registration and `change_role` accept only `attendee`
  or `organizer` (enforced by the request schemas), and nothing here reads a role from a
  token.
"""

import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import EventStatus, NotificationType, UserRole
from app.errors import AppError
from app.models import Event, OrganizerProfile, User
from app.schemas.auth import RegisterRequest
from app.security import (
    TokenType,
    create_token,
    decode_token,
    hash_password,
    password_fingerprint,
    verify_password,
)
from app.services import audit
from app.services.mail import Outbound, OutgoingEmail, render
from app.services.notifications import record_email


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(func.lower(User.email) == email.lower()))
    return result.scalar_one_or_none()


def _web_link(user: User, path: str, token: str) -> str:
    base = get_settings().public_base_url.rstrip("/")
    return f"{base}/{user.locale}/{path}?{urlencode({'token': token})}"


def _verification_email(user: User) -> OutgoingEmail:
    token = create_token(TokenType.VERIFY_EMAIL, user.id, email=user.email.lower())
    return render(
        "verify_email",
        user.locale,
        to=user.email,
        action_url=_web_link(user, "verify-email", token),
        name=user.full_name,
        hours=get_settings().email_verify_ttl_seconds // 3600,
    )


def _email_taken() -> AppError:
    return AppError(409, "email_taken", "This email is already registered. Sign in instead.")


def _add_organizer_profile(session: AsyncSession, user: User) -> None:
    session.add(
        OrganizerProfile(user_id=user.id, display_name=user.full_name, contact_email=user.email)
    )


async def register(session: AsyncSession, data: RegisterRequest) -> Outbound:
    # Hash first, whatever happens next, so both branches cost the same.
    hashed = await hash_password(data.password)
    if await get_user_by_email(session, data.email) is not None:
        raise _email_taken()

    user = User(
        email=data.email,
        hashed_password=hashed,
        full_name=data.full_name,
        role=UserRole(data.role),
        locale=data.locale,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        # Lost a race with a concurrent registration for the same email.
        await session.rollback()
        raise _email_taken() from None
    if user.role is UserRole.ORGANIZER:
        _add_organizer_profile(session, user)
    msg = _verification_email(user)
    notification = await record_email(
        session, user_id=user.id, type=NotificationType.ACCOUNT_VERIFICATION, msg=msg
    )
    await session.commit()
    return [(msg, notification.id)]


# Roles a user may switch between themselves. Platform admins are appointed, and event
# admins come from StaffAssignment, so neither can be chosen or left this way.
SELF_SERVICE_ROLES = frozenset({UserRole.ATTENDEE, UserRole.ORGANIZER})
# Events that are on sale or still have holders, so they need an organizer to manage them.
LIVE_EVENT_STATUSES = (EventStatus.PUBLISHED, EventStatus.UNPUBLISHED)


async def change_role(session: AsyncSession, user: User, role: UserRole) -> User:
    """Switch between attendee and organizer.

    The organizer profile is never deleted, so switching back restores the user's events,
    profile and payout account. Leaving the organizer role is refused while the user has
    live events, because nobody else could manage them.
    """
    if user.role not in SELF_SERVICE_ROLES or role not in SELF_SERVICE_ROLES:
        raise AppError(403, "role_change_not_allowed", "This account's role can't be changed.")
    if role is user.role:
        return user

    profile = await session.scalar(
        select(OrganizerProfile).where(OrganizerProfile.user_id == user.id)
    )
    if role is UserRole.ORGANIZER:
        if profile is None:
            _add_organizer_profile(session, user)
    elif profile is not None:
        live = await session.scalar(
            select(func.count())
            .select_from(Event)
            .where(Event.organizer_profile_id == profile.id, Event.status.in_(LIVE_EVENT_STATUSES))
        )
        if live:
            raise AppError(
                409,
                "organizer_has_active_events",
                "Cancel or finish your live events before switching to attendee.",
            )

    previous = user.role
    user.role = role
    audit.record(
        session,
        actor_id=user.id,
        action="user.role_changed",
        entity_type="user",
        entity_id=user.id,
        description=f"{previous} → {role}",
    )
    await session.commit()
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(session, email)
    ok = await verify_password(password, user.hashed_password if user else None)
    if user is None or not ok:
        raise AppError(401, "invalid_credentials", "The email or password is incorrect.")
    if user.is_suspended:
        raise AppError(403, "account_suspended", "This account has been suspended.")
    # Checked only after the password matched, so it never reveals whether an email is
    # registered.
    if not user.is_email_verified:
        raise AppError(403, "email_not_confirmed", "Confirm your email address before signing in.")
    return user


def issue_tokens(user: User) -> tuple[str, str]:
    """(access token, refresh token)."""
    access = create_token(TokenType.ACCESS, user.id)
    refresh = create_token(
        TokenType.REFRESH, user.id, pwd=password_fingerprint(user.hashed_password)
    )
    return access, refresh


async def user_from_refresh_token(session: AsyncSession, token: str) -> User:
    claims = decode_token(token, TokenType.REFRESH)
    user = await session.get(User, uuid.UUID(claims["sub"]))
    if (
        user is None
        or user.is_suspended
        or not user.is_email_verified
        or claims.get("pwd") != password_fingerprint(user.hashed_password)
    ):
        raise AppError(401, "unauthorized", "The session has ended. Please sign in again.")
    return user


async def verify_email(session: AsyncSession, token: str) -> tuple[User, bool]:
    """Confirm the address. Returns the user and whether this call confirmed it.

    Only the first confirmation signs the user in, so an old link from the inbox can't be
    used as a standing sign-in link.
    """
    claims = decode_token(token, TokenType.VERIFY_EMAIL)
    user = await session.get(User, uuid.UUID(claims["sub"]))
    # The link is bound to the address it was sent to.
    if user is None or claims.get("email") != user.email.lower():
        raise AppError(400, "invalid_token", "The token is invalid.")
    if user.is_email_verified:
        return user, False
    user.is_email_verified = True
    user.email_verified_at = datetime.now(UTC)
    await session.commit()
    return user, True


async def resend_verification(session: AsyncSession, email: str) -> Outbound:
    user = await get_user_by_email(session, email)
    if user is None or user.is_email_verified or user.is_suspended:
        return []
    msg = _verification_email(user)
    notification = await record_email(
        session, user_id=user.id, type=NotificationType.ACCOUNT_VERIFICATION, msg=msg
    )
    await session.commit()
    return [(msg, notification.id)]


async def forgot_password(session: AsyncSession, email: str) -> Outbound:
    user = await get_user_by_email(session, email)
    if user is None or user.is_suspended:
        return []
    token = create_token(
        TokenType.RESET_PASSWORD, user.id, pwd=password_fingerprint(user.hashed_password)
    )
    msg = render(
        "reset_password",
        user.locale,
        to=user.email,
        action_url=_web_link(user, "reset-password", token),
        name=user.full_name,
        minutes=get_settings().password_reset_ttl_seconds // 60,
    )
    # NotificationType has no password-reset member (SRS 4.10 does not list one), so this
    # email is sent without a Notification row.
    return [(msg, None)]


async def reset_password(session: AsyncSession, token: str, new_password: str) -> None:
    claims = decode_token(token, TokenType.RESET_PASSWORD)
    user = await session.get(User, uuid.UUID(claims["sub"]))
    # A used link no longer matches: the password hash, and so the fingerprint, changed.
    if user is None or claims.get("pwd") != password_fingerprint(user.hashed_password):
        raise AppError(400, "invalid_token", "The token is invalid.")
    user.hashed_password = await hash_password(new_password)
    await session.commit()
