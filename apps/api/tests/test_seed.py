"""The demo seed runs cleanly and is idempotent."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivationStatus, TicketStatus
from app.models import (
    CheckInRecord,
    Event,
    Order,
    PaidSalesActivation,
    PromoRedemption,
    Refund,
    SupportCase,
    Ticket,
    User,
)
from app.seed import JAZZ_SLUG, seed


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


async def test_seed_moves_stale_demo_events_forward(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    """A database seeded weeks ago still has an upcoming jazz night to buy and scan."""
    await seed()
    jazz = await session.scalar(select(Event).where(Event.slug == JAZZ_SLUG))
    assert jazz is not None
    # As if the seed ran a month ago: the jazz night ended yesterday.
    went_by = jazz.ends_at - (datetime.now(UTC) - timedelta(days=1))
    jazz.starts_at -= went_by
    jazz.ends_at -= went_by
    await session.commit()
    stale_local = jazz.starts_at.astimezone(ZoneInfo(jazz.timezone))
    listed = (await client.get("/api/v1/events")).json()["items"]
    assert JAZZ_SLUG not in [e["slug"] for e in listed]

    await seed()

    await session.refresh(jazz)
    assert jazz.starts_at - datetime.now(UTC) >= timedelta(days=14)
    local = jazz.starts_at.astimezone(ZoneInfo(jazz.timezone))
    assert (local.weekday(), local.time()) == (stale_local.weekday(), stale_local.time())
    listed = (await client.get("/api/v1/events")).json()["items"]
    assert JAZZ_SLUG in [e["slug"] for e in listed]
    # The past event stays in the past for the history views.
    past = await session.scalar(select(Event).where(Event.slug == "nauryz-spring-fair-demo"))
    assert past is not None and past.ends_at < datetime.now(UTC)
