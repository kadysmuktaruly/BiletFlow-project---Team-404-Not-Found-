"""Runtime platform settings (SRS 4.12). With no row in `platform_settings`, the environment
defaults apply, so a fresh deployment behaves exactly as configured in `.env`."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import PlatformSettings


async def current(session: AsyncSession) -> PlatformSettings | None:
    row: PlatformSettings | None = await session.scalar(select(PlatformSettings))
    return row


async def activation_fee_kzt(session: AsyncSession) -> int:
    """The fee for activations paid from now on. Fees already paid keep their amount."""
    row = await current(session)
    return row.activation_fee_kzt if row else get_settings().activation_fee_kzt
