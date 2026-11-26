"""Deleting your own account.

The SRS does not list account deletion (SRS 4.1 covers register, verify, sign in and out,
and reset password). It is added here so people can leave the platform.

The `users` row is not removed. Orders, tickets, payments, refunds, campaigns and support
cases reference it with ON DELETE RESTRICT, and the audit trail (SRS 4.16) is append-only.
Instead the account is **anonymised**:

* email, name, phone and password are replaced, so nobody can sign in to it, every token
  issued before is refused (`app.deps.get_current_user`, refresh), and the address is
  free to register again;
* in-app notifications are removed and live staff assignments are revoked;
* an organizer's contact details and payout holder name are cleared. The display name
  stays, because it is the public name printed on past events and their tickets.

Order records (including the attendee names typed in at checkout) are kept as the
platform's record of sales.
"""

import secrets
from datetime import UTC, datetime

from sqlalchemy import delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventStatus, UserRole
from app.errors import AppError
from app.models import Event, Notification, OrganizerProfile, PayoutAccount, StaffAssignment, User
from app.security import hash_password, verify_password
from app.services import audit

DELETED_NAME = "Deleted account"
DELETED_EMAIL_DOMAIN = "deleted.invalid"  # RFC 2606: can never receive mail.

# An event still in front of attendees. Cancel it (which refunds buyers) before leaving.
_LIVE_STATUSES = (EventStatus.PUBLISHED, EventStatus.UNPUBLISHED)


def deleted_email(user: User) -> str:
    return f"deleted-{user.id}@{DELETED_EMAIL_DOMAIN}"


async def _has_live_events(session: AsyncSession, profile_id: object, now: datetime) -> bool:
    live = (
        select(Event.id)
        .where(
            Event.organizer_profile_id == profile_id,
            Event.status.in_(_LIVE_STATUSES),
            Event.ends_at > now,
        )
        .limit(1)
    )
    return bool(await session.scalar(select(exists(live))))


async def delete_account(session: AsyncSession, user: User, password: str) -> None:
    if not await verify_password(password, user.hashed_password):
        raise AppError(400, "invalid_password", "The password is incorrect.")
    if user.role is UserRole.PLATFORM_ADMIN:
        raise AppError(409, "cannot_delete_admin", "Platform Admin accounts can't be deleted here.")

    now = datetime.now(UTC)
    profile = await session.scalar(
        select(OrganizerProfile).where(OrganizerProfile.user_id == user.id).with_for_update()
    )
    if profile is not None:
        if await _has_live_events(session, profile.id, now):
            raise AppError(
                409,
                "organizer_has_live_events",
                "Cancel or finish your published events before deleting your account.",
            )
        profile.contact_email = deleted_email(user)
        profile.contact_phone = None
        profile.description = None
        profile.website_url = None
        profile.logo_url = None
        await session.execute(
            update(PayoutAccount)
            .where(PayoutAccount.organizer_profile_id == profile.id)
            .values(account_holder_name=DELETED_NAME)
        )

    await session.execute(
        update(StaffAssignment)
        .where(StaffAssignment.user_id == user.id, StaffAssignment.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await session.execute(delete(Notification).where(Notification.user_id == user.id))

    user.email = deleted_email(user)
    user.full_name = DELETED_NAME
    user.phone = None
    # A random password nobody knows. Changing the hash also voids refresh tokens and
    # password-reset links, which carry its fingerprint.
    user.hashed_password = await hash_password(secrets.token_urlsafe(32))
    user.deleted_at = now

    audit.record(
        session,
        actor_id=user.id,
        action="user.account_deleted",
        entity_type="user",
        entity_id=user.id,
        description="Deleted their own account.",
    )
    await session.commit()
