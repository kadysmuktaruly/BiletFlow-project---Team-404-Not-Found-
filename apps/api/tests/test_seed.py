"""The demo seed runs cleanly and is idempotent."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivationStatus, TicketStatus
from app.models import Event, Order, PaidSalesActivation, Ticket, User
from app.seed import JAZZ_SLUG, seed


async def test_seed_is_idempotent(session: AsyncSession) -> None:
    await seed()
    await seed()
    assert await session.scalar(select(func.count()).select_from(User)) == 4
    assert await session.scalar(select(func.count()).select_from(Event)) == 2
    assert await session.scalar(select(func.count()).select_from(Order)) == 2
    statuses = list(await session.scalars(select(Ticket.status)))
    assert sorted(statuses) == sorted(
        [TicketStatus.VALID] * 3 + [TicketStatus.CANCELLED, TicketStatus.REFUNDED]
    )
    jazz = await session.scalar(select(Event).where(Event.slug == JAZZ_SLUG))
    assert jazz is not None
    activation = await session.scalar(
        select(PaidSalesActivation).where(PaidSalesActivation.event_id == jazz.id)
    )
    assert activation is not None and activation.status is ActivationStatus.ACTIVE
