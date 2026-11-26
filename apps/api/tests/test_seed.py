"""The demo seed runs cleanly and is idempotent."""

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import ActivationStatus, EventStatus, StaffRole, TicketStatus, UserRole
from app.models import (
    CheckInRecord,
    Event,
    Order,
    OrganizerProfile,
    PaidSalesActivation,
    PromoCode,
    PromoRedemption,
    Refund,
    StaffAssignment,
    SupportCase,
    Ticket,
    TicketType,
    User,
)
from app.schemas.order import OrderCreate, OrderItemInput
from app.security import hash_password, verify_password
from app.seed import (
    ADMIN_EMAIL,
    ATTENDEE_EMAIL,
    JAZZ_SLUG,
    ORGANIZER_EMAIL,
    PASSWORD,
    STAFF_EMAIL,
    seed,
)
from app.services import orders


async def test_seed_is_idempotent(session: AsyncSession) -> None:
    await seed()
    await seed()
    assert await session.scalar(select(func.count()).select_from(User)) == 6
    assert await session.scalar(select(func.count()).select_from(Event)) == 3
    assert await session.scalar(select(func.count()).select_from(Order)) == 4
    statuses = list(await session.scalars(select(Ticket.status)))
    assert sorted(statuses) == sorted(
        [TicketStatus.VALID] * 4
        + [TicketStatus.CHECKED_IN, TicketStatus.CANCELLED]
        + [TicketStatus.REFUNDED] * 2
    )
    # Reports 4-6 data: one campaign with one redemption, one refund, one support case.
    assert await session.scalar(select(func.count()).select_from(PromoRedemption)) == 1
    assert await session.scalar(select(func.count()).select_from(Refund)) == 1
    assert await session.scalar(select(func.count()).select_from(SupportCase)) == 1
    assert await session.scalar(select(func.count()).select_from(CheckInRecord)) == 1
    jazz = await session.scalar(select(Event).where(Event.slug == JAZZ_SLUG))
    assert jazz is not None
    activation = await session.scalar(
        select(PaidSalesActivation).where(PaidSalesActivation.event_id == jazz.id)
    )
    assert activation is not None and activation.status is ActivationStatus.ACTIVE


async def test_seed_creates_the_live_demo_cast(session: AsyncSession) -> None:
    await seed()
    roles = dict(
        (
            await session.execute(
                select(User.email, User.role).where(User.email.like("%@biletflow.demo"))
            )
        )
        .tuples()
        .all()
    )
    assert roles[ORGANIZER_EMAIL] is UserRole.ORGANIZER
    assert roles[ATTENDEE_EMAIL] is UserRole.ATTENDEE
    assert roles[ADMIN_EMAIL] is UserRole.PLATFORM_ADMIN
    # Door staff get check-in from the assignment, not from the platform role.
    assert roles[STAFF_EMAIL] is UserRole.ATTENDEE
    jazz = await session.scalar(select(Event).where(Event.slug == JAZZ_SLUG))
    assert jazz is not None and jazz.status is EventStatus.PUBLISHED
    owner = await session.scalar(
        select(User.email)
        .join(OrganizerProfile, OrganizerProfile.user_id == User.id)
        .where(OrganizerProfile.id == jazz.organizer_profile_id)
    )
    assert owner == ORGANIZER_EMAIL
    assigned = await session.scalar(
        select(User.email)
        .join(StaffAssignment, StaffAssignment.user_id == User.id)
        .where(StaffAssignment.event_id == jazz.id, StaffAssignment.role == StaffRole.EVENT_ADMIN)
    )
    assert assigned == STAFF_EMAIL
    standard = await session.scalar(
        select(TicketType).where(TicketType.event_id == jazz.id, TicketType.name == "Standard")
    )
    assert standard is not None and standard.price_kzt == 8000 and standard.quantity_total == 100
    # STUDENT20 is created live on stage, so the plain seed leaves it out.
    assert await session.scalar(select(PromoCode).where(PromoCode.code == "STUDENT20")) is None


async def test_backup_campaign_is_idempotent_and_takes_20_percent(session: AsyncSession) -> None:
    await seed(with_backup_campaign=True)
    await seed(with_backup_campaign=True)
    codes = list(await session.scalars(select(PromoCode).where(PromoCode.code == "STUDENT20")))
    assert len(codes) == 1

    attendee = await session.scalar(select(User).where(User.email == ATTENDEE_EMAIL))
    jazz = await session.scalar(select(Event).where(Event.slug == JAZZ_SLUG))
    assert attendee is not None and jazz is not None
    standard = await session.scalar(
        select(TicketType).where(TicketType.event_id == jazz.id, TicketType.name == "Standard")
    )
    assert standard is not None
    order, _ = await orders.create_order(
        session,
        attendee,
        OrderCreate(
            event_id=jazz.id,
            items=[OrderItemInput(ticket_type_id=standard.id, quantity=1)],
            promo_code="student20",
        ),
    )
    assert order.subtotal_kzt == 8000
    assert order.subtotal_kzt - order.discount_kzt == 6400


async def test_seed_renames_accounts_from_the_old_demo_domain(session: AsyncSession) -> None:
    # A database seeded before the rename, including the Reports 4-6 data.
    await seed()
    await session.execute(
        update(User).values(email=func.replace(User.email, "@biletflow.demo", "@demo.biletflow.kz"))
    )
    await session.execute(
        update(User)
        .where(User.email == "organizer@demo.biletflow.kz")
        .values(
            full_name="Old name",
            is_suspended=True,
            hashed_password=await hash_password("something-else-1"),
        )
    )
    await session.commit()
    await seed()
    await seed()
    session.expire_all()
    emails = set(await session.scalars(select(User.email)))
    assert emails == {
        ORGANIZER_EMAIL,
        ATTENDEE_EMAIL,
        STAFF_EMAIL,
        ADMIN_EMAIL,
        "aliya@biletflow.demo",
        "timur@biletflow.demo",
    }
    organizer = await session.scalar(select(User).where(User.email == ORGANIZER_EMAIL))
    assert organizer is not None
    assert organizer.full_name == "Alisher (Demo Organizer)"
    assert organizer.is_email_verified and not organizer.is_suspended
    assert await verify_password(PASSWORD, organizer.hashed_password)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("environment", "production"),
        ("environment", "staging"),
        (
            "database_url",
            "postgresql+asyncpg://postgres:x@db.abcd.supabase.co:5432/postgres",
        ),
    ],
)
async def test_seed_refuses_anything_but_a_local_database(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    monkeypatch.setattr(get_settings(), field, value)
    with pytest.raises(SystemExit, match="Refusing"):
        await seed()
    assert await session.scalar(select(func.count()).select_from(User)) == 0
