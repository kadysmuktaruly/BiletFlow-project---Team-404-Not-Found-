"""The demo seed runs cleanly and is idempotent."""

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
