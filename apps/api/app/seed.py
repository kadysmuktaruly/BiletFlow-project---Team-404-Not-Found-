"""Demo data for local runs and the course demo. Idempotent: running it twice changes nothing.

    uv run python -m app.seed                          # from apps/api
    docker compose exec api python -m app.seed
    docker compose exec api python -m app.seed --with-backup-campaign

Docker Compose runs it on start when SEED_DEMO_DATA=true (the default there). It refuses to
run unless ENVIRONMENT is development or test and the database is on this machine or in
Compose (`localhost`, `127.0.0.1`, `db`). Every account uses the same password, printed at
the end. Re-running it makes sure the four demo accounts can sign in: verified, not
suspended, and with that password.

What it creates:

* organizer@biletflow.demo (Alisher): an organizer with a verified email and a simulated
  payout account, owning two published events:
    - "Student Tech Meetup" (free, public)
    - "Almaty Jazz Night" (paid, public, paid sales activated through the DEMO fee payment;
      Standard 8,000 KZT x 100 and VIP 20,000 KZT x 20; kept at least a week in the future)
* attendee@biletflow.demo (Sanzhar): an attendee with one free registration and one
  DEMO-paid order.
* staff@biletflow.demo (Nurali): an Event Admin assigned to both events (for the scanner
  app). The platform role stays `attendee`; the assignment is what grants check-in.
* admin@biletflow.demo: a Platform Admin (never self-assignable, so it only comes from here).
* Fixtures for the scanner's five result screens: one cancelled and one refunded ticket.
* Reports 4-6: a campaign on the jazz night (code JAZZ15, 15%), aliya@biletflow.demo's
  promo purchase with one ticket checked in and a support case, timur@biletflow.demo's VIP
  order refunded by the organizer, and a past "Nauryz Spring Fair" for event history.
* With --with-backup-campaign: the live demo's STUDENT20 campaign (20%) on the jazz night,
  in case it can't be created on stage. Leave it off when the organizer creates it live.

Databases seeded before the switch to `@biletflow.demo` have the same accounts at
`@demo.biletflow.kz`; they are renamed in place, so nothing is duplicated.
"""

import argparse
import asyncio
import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
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
from app.security import hash_password, verify_password
from app.services import activation, orders, payments

PASSWORD = "Demo-pass-2026"
ALMATY = ZoneInfo("Asia/Almaty")
MEETUP_SLUG = "student-tech-meetup-demo"
JAZZ_SLUG = "almaty-jazz-night-demo"

DOMAIN = "biletflow.demo"
LEGACY_DOMAIN = "demo.biletflow.kz"
ORGANIZER_EMAIL = f"organizer@{DOMAIN}"
ATTENDEE_EMAIL = f"attendee@{DOMAIN}"
STAFF_EMAIL = f"staff@{DOMAIN}"
ADMIN_EMAIL = f"admin@{DOMAIN}"
BACKUP_CAMPAIGN_CODE = "STUDENT20"

_SAFE_ENVIRONMENTS = frozenset({"development", "test"})
_LOCAL_DB_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "db"})


def _refuse_unsafe_target() -> None:
    """Demo accounts share a published password, so never seed anything but a local DB."""
    settings = get_settings()
    if settings.environment not in _SAFE_ENVIRONMENTS:
        raise SystemExit(f"Refusing to seed demo data with ENVIRONMENT={settings.environment!r}.")
    host = make_url(settings.database_url).host or ""
    if host not in _LOCAL_DB_HOSTS:
        raise SystemExit(
            f"Refusing to seed demo data into a database at {host!r}: "
            "only a local or Docker Compose database is allowed."
        )


def _evening(days_ahead: int, hour: int) -> datetime:
    day = (datetime.now(ALMATY) + timedelta(days=days_ahead)).date()
    return datetime.combine(day, time(hour, 0), tzinfo=ALMATY)


async def _user(
    session: AsyncSession, email: str, name: str, role: UserRole, locale: str = "ru"
) -> User:
    user = await session.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        legacy = email.replace(f"@{DOMAIN}", f"@{LEGACY_DOMAIN}")
        user = await session.scalar(select(User).where(func.lower(User.email) == legacy))
        if user is not None:
            user.email = email
            user.full_name = name
    if user is not None:
        # Whatever a rehearsal did to the account, make sure it can sign in again.
        user.role = role
        if not user.is_email_verified:
            user.is_email_verified = True
            user.email_verified_at = datetime.now(UTC)
        user.is_suspended = False
        user.suspended_at = None
        if not await verify_password(PASSWORD, user.hashed_password):
            user.hashed_password = await hash_password(PASSWORD)
        await session.flush()
    else:
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


async def seed(*, with_backup_campaign: bool = False) -> None:
    _refuse_unsafe_target()

    async with SessionLocal() as session:
        organizer_user = await _user(
            session, ORGANIZER_EMAIL, "Alisher (Demo Organizer)", UserRole.ORGANIZER, "en"
        )
        attendee = await _user(
            session, ATTENDEE_EMAIL, "Sanzhar (Demo Attendee)", UserRole.ATTENDEE, "en"
        )
        staff = await _user(
            session, STAFF_EMAIL, "Nurali (Demo Door Staff)", UserRole.ATTENDEE, "en"
        )
        await _user(session, ADMIN_EMAIL, "Demo Admin", UserRole.PLATFORM_ADMIN, "en")

        organizer = await session.scalar(
            select(OrganizerProfile).where(OrganizerProfile.user_id == organizer_user.id)
        )
        if organizer is None:
            organizer = OrganizerProfile(
                user_id=organizer_user.id,
                display_name="Almaty Events Collective",
                contact_email=f"hello@{DOMAIN}",
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
                    account_holder_name="Alisher (Demo Organizer)",
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
        # The seeded date is relative to the first run, so an old database can hold a jazz
        # night that has already happened. Keep it at least a week ahead for the live demo.
        if jazz.starts_at < datetime.now(UTC) + timedelta(days=7):
            length = jazz.ends_at - jazz.starts_at
            jazz.starts_at = _evening(21, 19)
            jazz.ends_at = jazz.starts_at + length
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

        await _report_6_data(session, organizer, organizer_user, staff, jazz)
        backup_url = (
            await _backup_campaign(session, organizer_user, jazz) if with_backup_campaign else None
        )

    print("Demo data ready. Password for every account:", PASSWORD)
    for email in (
        ORGANIZER_EMAIL,
        ATTENDEE_EMAIL,
        f"aliya@{DOMAIN}",
        f"timur@{DOMAIN}",
        STAFF_EMAIL,
        ADMIN_EMAIL,
    ):
        print("  ", email)
    if backup_url:
        print(f"Backup campaign {BACKUP_CAMPAIGN_CODE} (20%):", backup_url)


async def _backup_campaign(session: AsyncSession, organizer_user: User, jazz: Event) -> str:
    """The live demo's STUDENT20 campaign, through the same service the organizer's
    Campaigns page uses. Returns the campaign link (the Campaign QR's target)."""
    from app.enums import DiscountType
    from app.models import PromoCode, PromotionalCampaign
    from app.schemas.promo import CampaignCreate
    from app.services import promotions

    code = await session.scalar(
        select(PromoCode).where(func.lower(PromoCode.code) == BACKUP_CAMPAIGN_CODE.lower())
    )
    if code is None:
        campaign = await promotions.create(
            session,
            jazz,
            organizer_user,
            CampaignCreate(
                name="Students 20%",
                discount_type=DiscountType.PERCENTAGE,
                discount_percent=20,
                code=BACKUP_CAMPAIGN_CODE,
            ),
        )
    else:
        found = await session.get(PromotionalCampaign, code.campaign_id)
        assert found is not None
        campaign = found
    return promotions.campaign_url(campaign)


async def _report_6_data(
    session: AsyncSession,
    organizer: OrganizerProfile,
    organizer_user: User,
    staff: User,
    jazz: Event,
) -> None:
    """Data that shows Reports 4-6 in the demo: a campaign and a promo sale, a refund, a
    check-in, a support case and a past event. Everything goes through the normal services,
    so it's exactly what the app would have recorded. Runs once (keyed on the campaign)."""
    from app.deps import StaffAccess
    from app.enums import DiscountType, SupportCategory
    from app.models import PromoCode
    from app.schemas.promo import CampaignCreate
    from app.schemas.support import CaseCreate, MessageCreate
    from app.services import checkin, promotions, refunds, support

    aliya = await _user(session, f"aliya@{DOMAIN}", "Aliya Bekova", UserRole.ATTENDEE, "ru")
    timur = await _user(session, f"timur@{DOMAIN}", "Timur Akhmetov", UserRole.ATTENDEE, "en")
    if await session.scalar(select(PromoCode).where(PromoCode.code == "JAZZ15")) is not None:
        await session.commit()
        return
    await promotions.create(
        session,
        jazz,
        organizer_user,
        CampaignCreate(
            name="Students 15%",
            discount_type=DiscountType.PERCENTAGE,
            discount_percent=15,
            code="JAZZ15",
            max_redemptions=50,
        ),
    )
    standard = await session.scalar(
        select(TicketType).where(TicketType.event_id == jazz.id, TicketType.name == "Standard")
    )
    vip = await session.scalar(
        select(TicketType).where(TicketType.event_id == jazz.id, TicketType.name == "VIP")
    )
    assert standard and vip

    # A promo sale, as if Aliya came through the Campaign QR.
    promo_order, _ = await orders.create_order(
        session,
        aliya,
        OrderCreate(
            event_id=jazz.id,
            items=[OrderItemInput(ticket_type_id=standard.id, quantity=2)],
            promo_code="jazz15",
        ),
    )
    await payments.pay_order(session, aliya, promo_order.id, "seed-aliya-payment", "succeed")

    # A VIP order the organizer refunds in full (DEMO).
    vip_order, _ = await orders.create_order(
        session,
        timur,
        OrderCreate(event_id=jazz.id, items=[OrderItemInput(ticket_type_id=vip.id, quantity=1)]),
    )
    await payments.pay_order(session, timur, vip_order.id, "seed-timur-payment", "succeed")
    await refunds.refund_order(
        session, organizer_user, jazz, vip_order.id, "seed-timur-refund", "Can't attend"
    )

    # Aliya's first ticket is scanned in by the Event Admin.
    first = await session.scalar(
        select(Ticket).where(Ticket.order_id == promo_order.id).order_by(Ticket.id).limit(1)
    )
    assert first
    access = StaffAccess(event=jazz, user=staff, role="event_admin")
    await checkin.scan(session, access, first.admission_token, "seed-door-phone")

    # A support case from Aliya's order, answered by the organizer.
    case, _ = await support.create_case(
        session,
        aliya,
        CaseCreate(
            category=SupportCategory.TICKET_DELIVERY,
            subject="Second ticket for my friend",
            message="Can my friend show the second QR on her own phone?",
            order_id=promo_order.id,
        ),
    )
    await support.add_message(
        session,
        organizer_user,
        case.id,
        MessageCreate(body="Yes. Forward her the PDF; each QR admits one person once."),
    )

    # A past event for the Completed view in event history.
    past, past_new = await _event(
        session,
        organizer,
        slug="nauryz-spring-fair-demo",
        title="Nauryz Spring Fair",
        description="A spring fair with music, crafts and food.",
        category="Festival",
        venue=Venue(name="Central Park", address_line1="Gogol St 1", city="Almaty"),
        starts_at=_evening(-30, 12),
        hours=6,
    )
    if past_new:
        session.add(
            TicketType(event_id=past.id, name="Free entry", price_kzt=0, quantity_total=500)
        )
    await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.seed", description="Load BiletFlow demo data (local only)."
    )
    parser.add_argument(
        "--with-backup-campaign",
        action="store_true",
        help=f"also create the live demo's {BACKUP_CAMPAIGN_CODE} campaign (20%%) as a fallback",
    )
    args = parser.parse_args()
    asyncio.run(seed(with_backup_campaign=args.with_backup_campaign))


if __name__ == "__main__":
    main()
