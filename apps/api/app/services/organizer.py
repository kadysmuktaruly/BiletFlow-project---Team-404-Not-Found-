"""Organizer profile and simulated payout account (SRS 4.1, SRS 3.2 step 4)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import PayoutAccountStatus
from app.models import OrganizerProfile, PayoutAccount, User
from app.schemas.organizer import OrganizerProfileUpdate, PayoutAccountUpsert


async def get_or_create_profile(session: AsyncSession, user: User) -> OrganizerProfile:
    """Registration creates the profile; this also covers organizers created another way
    (seed data, a future admin promotion)."""
    profile = await session.scalar(
        select(OrganizerProfile).where(OrganizerProfile.user_id == user.id)
    )
    if profile is None:
        profile = OrganizerProfile(
            user_id=user.id, display_name=user.full_name, contact_email=user.email
        )
        session.add(profile)
        await session.flush()
    return profile


async def update_profile(
    session: AsyncSession, profile: OrganizerProfile, data: OrganizerProfileUpdate
) -> OrganizerProfile:
    for field, value in data.model_dump(mode="json").items():
        setattr(profile, field, value)
    await session.commit()
    return profile


async def get_payout_account(
    session: AsyncSession, profile: OrganizerProfile
) -> PayoutAccount | None:
    result = await session.scalars(
        select(PayoutAccount)
        .where(PayoutAccount.organizer_profile_id == profile.id)
        .order_by(PayoutAccount.created_at.desc())
        .limit(1)
    )
    return result.first()


async def upsert_payout_account(
    session: AsyncSession, profile: OrganizerProfile, data: PayoutAccountUpsert
) -> PayoutAccount:
    """Simulated verification: the account is marked verified at once. Real KYC/KYB and
    payouts are out of the MVP (SRS 8), and the record says so with `is_simulated`."""
    account = await get_payout_account(session, profile)
    if account is None:
        account = PayoutAccount(organizer_profile_id=profile.id)
        session.add(account)
    account.account_holder_name = data.account_holder_name
    account.bank_name = data.bank_name
    account.account_last4 = data.account_last4
    account.status = PayoutAccountStatus.VERIFIED
    account.verified_at = datetime.now(UTC)
    account.is_simulated = True
    await session.commit()
    return account
