"""Demo data for local runs and the course demo. Idempotent: running it twice changes nothing.

    uv run python -m app.seed            # from apps/api
    docker compose exec api python -m app.seed

Docker Compose runs it on start when SEED_DEMO_DATA=true (the default there). It refuses to
run when ENVIRONMENT=production. Every account uses the same password, printed at the end.

What it creates:

* organizer@demo.biletflow.kz: an organizer with a verified email and a simulated payout
  account, owning two published events:
    - "Student Tech Meetup" (free, public)
    - "Almaty Jazz Night" (paid, public, paid sales activated through the DEMO fee payment)
* attendee@demo.biletflow.kz: an attendee with one free registration and one DEMO-paid order.
* staff@demo.biletflow.kz: an Event Admin assigned to both events (for the scanner app).
* admin@demo.biletflow.kz: a Platform Admin (never self-assignable, so it only comes from here).
* Fixtures for the scanner's five result screens: one cancelled and one refunded ticket.
"""

import asyncio
import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import SessionLocal
from app.enums import (
    EventStatus,
    EventVisibility,
    PayoutAccountStatus,
    StaffRole,
    TicketStatus,
    UserRole,
)
from app.models import (
    Event,
    Order,
    OrganizerProfile,
    PayoutAccount,
    StaffAssignment,
    Ticket,
    TicketType,
    User,
    Venue,
)
from app.schemas.order import AttendeeInput, OrderCreate, OrderItemInput
from app.security import hash_password
from app.services import activation, orders, payments

PASSWORD = "Demo-pass-2026"
ALMATY = ZoneInfo("Asia/Almaty")
MEETUP_SLUG = "student-tech-meetup-demo"
JAZZ_SLUG = "almaty-jazz-night-demo"


def _evening(days_ahead: int, hour: int) -> datetime:
    day = (datetime.now(ALMATY) + timedelta(days=days_ahead)).date()
    return datetime.combine(day, time(hour, 0), tzinfo=ALMATY)


async def _user(
    session: AsyncSession, email: str, name: str, role: UserRole, locale: str = "ru"
) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            hashed_password=await hash_password(PASSWORD),
            full_name=name,
            role=role,
            locale=locale,
            is_email_verified=True,
            email_verified_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()
    return user


async def _event(
    session: AsyncSession,
    organizer: OrganizerProfile,
    *,
    slug: str,
    title: str,
    description: str,
    category: str,
    venue: Venue,
    starts_at: datetime,
    hours: int,
) -> tuple[Event, bool]:
    event = await session.scalar(select(Event).where(Event.slug == slug))
    if event is not None:
        return event, False
    session.add(venue)
    await session.flush()
    event = Event(
        organizer_profile_id=organizer.id,
        venue_id=venue.id,
        title=title,
        slug=slug,
        description=description,
        category=category,
        status=EventStatus.PUBLISHED,
        visibility=EventVisibility.PUBLIC,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=hours),
        timezone="Asia/Almaty",
        published_at=datetime.now(UTC),
    )
    session.add(event)
    await session.flush()
    return event, True


async def _assign(
    session: AsyncSession, event: Event, staff: User, by: User, role: StaffRole
) -> None:
    exists = await session.scalar(
        select(StaffAssignment).where(
            StaffAssignment.event_id == event.id,
            StaffAssignment.user_id == staff.id,
            StaffAssignment.revoked_at.is_(None),
        )
    )
    if exists is None:
        session.add(
            StaffAssignment(
                event_id=event.id, user_id=staff.id, role=role, assigned_by_user_id=by.id
            )
        )


async def seed() -> None:
    if get_settings().environment == "production":
        raise SystemExit("Refusing to seed demo data with ENVIRONMENT=production.")

    async with SessionLocal() as session:
        organizer_user = await _user(
            session, "organizer@demo.biletflow.kz", "Aruzhan Seitkali", UserRole.ORGANIZER
        )
        attendee = await _user(
            session, "attendee@demo.biletflow.kz", "Daniyar Kassymov", UserRole.ATTENDEE, "kk"
        )
        staff = await _user(
            session, "staff@demo.biletflow.kz", "Madina Ospanova", UserRole.ATTENDEE
        )
        await _user(
            session, "admin@demo.biletflow.kz", "BiletFlow Admin", UserRole.PLATFORM_ADMIN, "en"
        )

        organizer = await session.scalar(
            select(OrganizerProfile).where(OrganizerProfile.user_id == organizer_user.id)
        )
        if organizer is None:
            organizer = OrganizerProfile(
                user_id=organizer_user.id,
                display_name="Almaty Events Collective",
                contact_email="hello@demo.biletflow.kz",
                contact_phone="+7 700 000 00 00",
                description="Student meetups and live music in Almaty.",
            )
            session.add(organizer)
            await session.flush()
        if (
            await session.scalar(
                select(PayoutAccount).where(PayoutAccount.organizer_profile_id == organizer.id)
            )
            is None
        ):
            session.add(
                PayoutAccount(
                    organizer_profile_id=organizer.id,
                    account_holder_name="Aruzhan Seitkali",
                    bank_name="Demo Bank",
                    account_last4="4321",
                    status=PayoutAccountStatus.VERIFIED,
                    verified_at=datetime.now(UTC),
                    is_simulated=True,
                )
            )
            await session.flush()

        meetup, meetup_new = await _event(
            session,
            organizer,
            slug=MEETUP_SLUG,
            title="Student Tech Meetup",
            description="Lightning talks from students at Almaty universities, then pizza.\n"
            "Free entry; please register so we know how many to expect.",
            category="Technology",
            venue=Venue(name="Astana Hub Almaty", address_line1="Al-Farabi Ave 17", city="Almaty"),
            starts_at=_evening(14, 18),
            hours=3,
        )
        if meetup_new:
            session.add(
                TicketType(
                    event_id=meetup.id,
                    name="Free registration",
                    price_kzt=0,
                    quantity_total=200,
                    max_per_order=4,
                )
            )

        jazz, jazz_new = await _event(
            session,
            organizer,
            slug=JAZZ_SLUG,
            title="Almaty Jazz Night",
            description="An evening of Kazakh and international jazz standards.",
            category="Music",
            venue=Venue(name="Esentai Hall", address_line1="Al-Farabi Ave 77/8", city="Almaty"),
            starts_at=_evening(21, 19),
            hours=3,
        )
        if jazz_new:
            session.add_all(
                [
                    TicketType(
                        event_id=jazz.id,
                        name="Standard",
                        price_kzt=8000,
                        quantity_total=100,
                        max_per_order=6,
                    ),
                    TicketType(
                        event_id=jazz.id,
                        name="VIP",
                        price_kzt=20000,
                        quantity_total=20,
                        max_per_order=4,
                    ),
                ]
            )
        await session.flush()

        await _assign(session, meetup, staff, organizer_user, StaffRole.EVENT_ADMIN)
        await _assign(session, jazz, staff, organizer_user, StaffRole.EVENT_ADMIN)
        await session.commit()

        # Paid sales for the jazz night, through the real checklist and DEMO fee payment.
        await activation.verify_identity(session, jazz, organizer_user)
        await activation.connect_payout_account(session, jazz, organizer_user)
        await activation.accept_terms(session, jazz, organizer_user)
        state = await activation.read(session, await activation.get_or_create(session, jazz))
        if not state.activation_fee_paid:
            await activation.pay_fee(
                session, jazz, organizer_user, "seed-activation-fee", "succeed"
            )

        # The attendee's orders, made through the normal checkout (no emails are sent here).
        if await session.scalar(select(Order).where(Order.user_id == attendee.id)) is None:
            free_type = await session.scalar(
                select(TicketType).where(TicketType.event_id == meetup.id)
            )
            standard = await session.scalar(
                select(TicketType).where(
                    TicketType.event_id == jazz.id, TicketType.name == "Standard"
                )
            )
            assert free_type and standard
            await orders.create_order(
                session,
                attendee,
                OrderCreate(
                    event_id=meetup.id,
                    items=[OrderItemInput(ticket_type_id=free_type.id, quantity=2)],
                    attendees=[
                        AttendeeInput(full_name=attendee.full_name, email=attendee.email),
                        AttendeeInput(full_name="Aigerim Nurlanqyzy"),
                    ],
                ),
            )
            paid_order, _ = await orders.create_order(
                session,
                attendee,
                OrderCreate(
                    event_id=jazz.id,
                    items=[OrderItemInput(ticket_type_id=standard.id, quantity=3)],
                ),
            )
            await payments.pay_order(
                session, attendee, paid_order.id, f"seed-{uuid.uuid4()}", "succeed"
            )

            # Scanner fixtures: the second meetup ticket is cancelled, one jazz ticket refunded.
            # (Refunds as a workflow arrive with SRS 4.9; this only sets the status to scan.)
            now = datetime.now(UTC)
            meetup_tickets = list(
                await session.scalars(
                    select(Ticket).where(Ticket.event_id == meetup.id).order_by(Ticket.id)
                )
            )
            meetup_tickets[-1].status = TicketStatus.CANCELLED
            meetup_tickets[-1].cancelled_at = now
            jazz_ticket = await session.scalar(
                select(Ticket)
                .where(Ticket.order_id == paid_order.id)
                .order_by(Ticket.id.desc())
                .limit(1)
            )
            assert jazz_ticket
            jazz_ticket.status = TicketStatus.REFUNDED
            jazz_ticket.refunded_at = now
            await session.commit()

    print("Demo data ready. Password for every account:", PASSWORD)
    for email in (
        "organizer@demo.biletflow.kz",
        "attendee@demo.biletflow.kz",
        "staff@demo.biletflow.kz",
        "admin@demo.biletflow.kz",
    ):
        print("  ", email)


if __name__ == "__main__":
    asyncio.run(seed())
