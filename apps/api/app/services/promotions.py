"""Promotional campaigns and promo codes (SRS 4.14).

* **Server-side discounts only.** Attendees send a code; the discount comes from the
  campaign row. Percentages round down to whole KZT per line. A fixed discount is capped at
  the eligible subtotal and split across eligible lines in proportion to their value.
* **The redemption limit holds under concurrency.** A code is redeemed with one conditional
  ``UPDATE promo_codes SET redeemed_count = redeemed_count + 1 WHERE … redeemed_count <
  max_redemptions``, and `ck_promo_codes_within_limit` rejects anything past the limit in the
  database. The count includes orders still awaiting payment, and goes back down when such an
  order fails, expires or is abandoned (docs/decisions.md).
* **Campaign QR links carry an opaque `BFC1.` token**, never a price or discount. The
  check-in endpoint never accepts one (`app.services.checkin`).
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import CampaignStatus, DiscountType, EventStatus, EventVisibility, OrderStatus
from app.errors import AppError
from app.models import (
    Event,
    Order,
    PromoCode,
    PromoCodeTicketType,
    PromoRedemption,
    PromotionalCampaign,
    Ticket,
    TicketType,
    User,
)
from app.schemas.event import localize
from app.schemas.order import OrderItemInput
from app.schemas.promo import (
    CampaignCreate,
    CampaignRead,
    CampaignReport,
    CampaignResolution,
    CampaignUpdate,
    EffectiveStatus,
    PromoLine,
    PromoQuote,
    PromoRejection,
    PromoValidateRequest,
)
from app.services import audit

CAMPAIGN_TOKEN_PREFIX = "BFC1."
_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_MESSAGES: dict[PromoRejection, tuple[int, str]] = {
    "promo_not_found": (404, "This promo code doesn't exist for this event."),
    "promo_disabled": (409, "This promo code has been disabled."),
    "promo_not_started": (409, "This promo code isn't valid yet."),
    "promo_expired": (409, "This promo code has expired."),
    "promo_exhausted": (409, "This promo code has been used the maximum number of times."),
    "promo_not_applicable": (409, "This promo code doesn't apply to the selected tickets."),
}
# Orders that count as sales in campaign reporting (SRS 4.14).
_SOLD = (OrderStatus.CONFIRMED, OrderStatus.REFUNDED)


def reject(reason: PromoRejection) -> AppError:
    status, message = _MESSAGES[reason]
    return AppError(status, reason, message)


def campaign_url(campaign: PromotionalCampaign) -> str:
    """The link a Campaign QR encodes (SRS 4.14: "a trackable HTTPS event link containing an
    opaque campaign or promo token")."""
    return f"{get_settings().public_base_url.rstrip('/')}/c/{campaign.qr_token}"


def _new_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


def _new_token() -> str:
    return CAMPAIGN_TOKEN_PREFIX + secrets.token_urlsafe(16)


# --- rules --------------------------------------------------------------------------------


def effective_status(
    campaign: PromotionalCampaign, code: PromoCode, now: datetime | None = None
) -> EffectiveStatus:
    now = now or datetime.now(UTC)
    if campaign.status is CampaignStatus.DISABLED or not code.is_active:
        return "disabled"
    if campaign.ends_at is not None and now >= campaign.ends_at:
        return "expired"
    if code.max_redemptions is not None and code.redeemed_count >= code.max_redemptions:
        return "exhausted"
    if campaign.starts_at is not None and now < campaign.starts_at:
        return "scheduled"
    return "active"


_REJECTION_FOR: dict[EffectiveStatus, PromoRejection | None] = {
    "active": None,
    "disabled": "promo_disabled",
    "expired": "promo_expired",
    "exhausted": "promo_exhausted",
    "scheduled": "promo_not_started",
}


def _usability(
    campaign: PromotionalCampaign, code: PromoCode, now: datetime
) -> PromoRejection | None:
    return _REJECTION_FOR[effective_status(campaign, code, now)]


@dataclass
class AppliedPromo:
    code: PromoCode
    campaign: PromotionalCampaign
    # One discount per input line, in the same order.
    discounts: list[int]

    @property
    def total_discount(self) -> int:
        return sum(self.discounts)


async def find_code(
    session: AsyncSession, event_id: uuid.UUID, text: str
) -> tuple[PromoCode, PromotionalCampaign]:
    """Case-insensitive (SRS 4.14). A code of another event is "not found" here."""
    row = (
        await session.execute(
            select(PromoCode, PromotionalCampaign)
            .join(PromotionalCampaign, PromotionalCampaign.id == PromoCode.campaign_id)
            .where(
                func.lower(PromoCode.code) == text.strip().lower(),
                PromotionalCampaign.event_id == event_id,
            )
        )
    ).first()
    if row is None:
        raise reject("promo_not_found")
    code, campaign = row
    return code, campaign


async def _eligible_type_ids(session: AsyncSession, code_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        await session.scalars(
            select(PromoCodeTicketType.ticket_type_id).where(
                PromoCodeTicketType.promo_code_id == code_id
            )
        )
    )


def compute_discounts(
    campaign: PromotionalCampaign,
    lines: list[tuple[uuid.UUID, int]],  # (ticket_type_id, line subtotal in KZT)
    eligible: set[uuid.UUID],
) -> list[int]:
    """Discount per line. `eligible` empty means every ticket type qualifies."""
    is_eligible = [not eligible or tt_id in eligible for tt_id, _ in lines]
    eligible_subtotal = sum(
        amount for (_, amount), ok in zip(lines, is_eligible, strict=True) if ok
    )
    if eligible_subtotal <= 0:
        raise reject("promo_not_applicable")
    if campaign.discount_type is DiscountType.PERCENTAGE:
        percent = campaign.discount_percent or 0
        return [
            amount * percent // 100 if ok else 0
            for (_, amount), ok in zip(lines, is_eligible, strict=True)
        ]
    # Fixed KZT: cap at the eligible subtotal, split proportionally, remainder to the last line.
    total = min(campaign.discount_kzt or 0, eligible_subtotal)
    discounts = [
        total * amount // eligible_subtotal if ok else 0
        for (_, amount), ok in zip(lines, is_eligible, strict=True)
    ]
    last = max(i for i, ok in enumerate(is_eligible) if ok and lines[i][1] > 0)
    discounts[last] += total - sum(discounts)
    return discounts


async def apply_to_lines(
    session: AsyncSession,
    event_id: uuid.UUID,
    text: str,
    lines: list[tuple[uuid.UUID, int]],
    now: datetime,
) -> AppliedPromo:
    """Validate a code against these lines and compute the discounts, without redeeming."""
    code, campaign = await find_code(session, event_id, text)
    rejection = _usability(campaign, code, now)
    if rejection is not None:
        raise reject(rejection)
    discounts = compute_discounts(campaign, lines, await _eligible_type_ids(session, code.id))
    return AppliedPromo(code=code, campaign=campaign, discounts=discounts)


async def redeem(session: AsyncSession, applied: AppliedPromo) -> None:
    """Take one redemption, atomically. Call in the checkout transaction."""
    taken = await session.scalar(
        update(PromoCode)
        .where(
            PromoCode.id == applied.code.id,
            PromoCode.is_active.is_(True),
            (PromoCode.max_redemptions.is_(None))
            | (PromoCode.redeemed_count < PromoCode.max_redemptions),
        )
        .values(redeemed_count=PromoCode.redeemed_count + 1)
        .returning(PromoCode.id)
    )
    if taken is None:
        raise reject("promo_exhausted")


async def release(session: AsyncSession, order: Order) -> None:
    """Give back the redemption held by an order that never confirmed."""
    if order.promo_code_id is None:
        return
    await session.execute(
        update(PromoCode)
        .where(PromoCode.id == order.promo_code_id, PromoCode.redeemed_count > 0)
        .values(redeemed_count=PromoCode.redeemed_count - 1)
    )


def record_redemption(session: AsyncSession, order: Order, now: datetime) -> None:
    """Write the PromoRedemption row when an order with a code is confirmed."""
    if order.promo_code_id is None or order.campaign_id is None:
        return
    session.add(
        PromoRedemption(
            promo_code_id=order.promo_code_id,
            campaign_id=order.campaign_id,
            order_id=order.id,
            user_id=order.user_id,
            discount_kzt=order.discount_kzt,
            order_total_kzt=order.total_kzt,
            redeemed_at=now,
        )
    )


# --- public: validate and resolve -------------------------------------------------------


async def _visible_event(session: AsyncSession, event_id: uuid.UUID, user: User | None) -> Event:
    from app.services.orders import is_owner_or_staff

    event = await session.get(Event, event_id)
    if event is None or event.status is not EventStatus.PUBLISHED or event.is_suspended:
        raise AppError(404, "event_not_found", "Event not found.")
    if event.visibility is EventVisibility.PRIVATE and not await is_owner_or_staff(
        session, event, user
    ):
        raise AppError(404, "event_not_found", "Event not found.")
    return event


async def quote(session: AsyncSession, user: User | None, data: PromoValidateRequest) -> PromoQuote:
    """SRS 4.14: show the applied code, the discount and the new total before checkout."""
    event = await _visible_event(session, data.event_id, user)
    lines = await _priced_lines(session, event, data.items)
    applied = await apply_to_lines(
        session, event.id, data.code, [(tt, amount) for tt, _, amount in lines], datetime.now(UTC)
    )
    subtotal = sum(amount for _, _, amount in lines)
    return PromoQuote(
        code=applied.code.code,
        campaign_name=applied.campaign.name,
        discount_type=applied.campaign.discount_type,
        discount_percent=applied.campaign.discount_percent,
        discount_kzt=applied.total_discount,
        subtotal_kzt=subtotal,
        total_kzt=subtotal - applied.total_discount,
        lines=[
            PromoLine(
                ticket_type_id=tt,
                quantity=qty,
                line_subtotal_kzt=amount,
                discount_kzt=discount,
                line_total_kzt=amount - discount,
            )
            for (tt, qty, amount), discount in zip(lines, applied.discounts, strict=True)
        ],
    )


async def _priced_lines(
    session: AsyncSession, event: Event, items: list[OrderItemInput]
) -> list[tuple[uuid.UUID, int, int]]:
    types = {
        t.id: t
        for t in await session.scalars(
            select(TicketType).where(
                TicketType.event_id == event.id,
                TicketType.id.in_({i.ticket_type_id for i in items}),
                TicketType.is_hidden.is_(False),
            )
        )
    }
    lines = []
    for item in items:
        tt = types.get(item.ticket_type_id)
        if tt is None:
            raise AppError(404, "ticket_type_not_found", "Ticket type not found.")
        lines.append((tt.id, item.quantity, tt.price_kzt * item.quantity))
    return lines


async def resolve(session: AsyncSession, token: str, user: User | None) -> CampaignResolution:
    """SRS 4.14 / UC10: a Campaign QR opens the right event with its code applied, after the
    server checks the campaign can be used. Ticket choice comes later, so applicability to
    specific ticket types is checked at quote and checkout time."""
    campaign = await session.scalar(
        select(PromotionalCampaign).where(PromotionalCampaign.qr_token == token.strip())
    )
    if campaign is None:
        raise AppError(404, "campaign_not_found", "This campaign link isn't valid.")
    event = await _visible_event(session, campaign.event_id, user)
    code = await session.scalar(
        select(PromoCode).where(PromoCode.campaign_id == campaign.id).order_by(PromoCode.created_at)
    )
    if code is None:
        raise AppError(404, "campaign_not_found", "This campaign link isn't valid.")
    rejection = _usability(campaign, code, datetime.now(UTC))
    return CampaignResolution(
        event_id=event.id,
        event_slug=event.slug,
        code=None if rejection else code.code,
        campaign_name=campaign.name,
        rejection=rejection,
    )


# --- organizer: manage and report ---------------------------------------------------------


async def _report(session: AsyncSession, campaign_id: uuid.UUID) -> CampaignReport:
    totals = (
        await session.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.subtotal_kzt), 0),
                func.coalesce(func.sum(Order.discount_kzt), 0),
                func.coalesce(func.sum(Order.total_kzt - Order.refunded_kzt), 0),
            ).where(Order.campaign_id == campaign_id, Order.status.in_(_SOLD))
        )
    ).one()
    tickets = await session.scalar(
        select(func.count(Ticket.id))
        .join(Order, Order.id == Ticket.order_id)
        .where(Order.campaign_id == campaign_id, Order.status.in_(_SOLD))
    )
    redemptions = await session.scalar(
        select(func.count(PromoRedemption.id)).where(PromoRedemption.campaign_id == campaign_id)
    )
    orders, gross, discount, net = totals
    return CampaignReport(
        redemptions=redemptions or 0,
        orders=orders,
        tickets_sold=tickets or 0,
        gross_revenue_kzt=gross,
        discount_kzt=discount,
        net_revenue_kzt=net,
    )


async def to_read(session: AsyncSession, campaign: PromotionalCampaign) -> CampaignRead:
    code = await session.scalar(
        select(PromoCode)
        .where(PromoCode.campaign_id == campaign.id)
        .order_by(PromoCode.created_at)
        .execution_options(populate_existing=True)
    )
    assert code is not None, "every campaign is created with its code"
    return CampaignRead(
        id=campaign.id,
        event_id=campaign.event_id,
        name=campaign.name,
        description=campaign.description,
        discount_type=campaign.discount_type,
        discount_percent=campaign.discount_percent,
        discount_kzt=campaign.discount_kzt,
        starts_at=campaign.starts_at,
        ends_at=campaign.ends_at,
        code=code.code,
        max_redemptions=code.max_redemptions,
        redeemed_count=code.redeemed_count,
        ticket_type_ids=sorted(await _eligible_type_ids(session, code.id)),
        status=effective_status(campaign, code),
        campaign_url=campaign_url(campaign),
        qr_token=campaign.qr_token,
        created_at=campaign.created_at,
        disabled_at=campaign.disabled_at,
        report=await _report(session, campaign.id),
    )


async def list_for_event(session: AsyncSession, event: Event) -> list[CampaignRead]:
    campaigns = await session.scalars(
        select(PromotionalCampaign)
        .where(PromotionalCampaign.event_id == event.id)
        .order_by(PromotionalCampaign.created_at.desc())
    )
    return [await to_read(session, c) for c in campaigns]


async def get_for_event(
    session: AsyncSession, event: Event, campaign_id: uuid.UUID
) -> PromotionalCampaign:
    campaign = await session.scalar(
        select(PromotionalCampaign).where(
            PromotionalCampaign.id == campaign_id, PromotionalCampaign.event_id == event.id
        )
    )
    if campaign is None:
        raise AppError(404, "campaign_not_found", "Campaign not found.")
    return campaign


async def _code_taken(session: AsyncSession, text: str) -> bool:
    return bool(
        await session.scalar(select(PromoCode.id).where(func.lower(PromoCode.code) == text.lower()))
    )


async def create(
    session: AsyncSession, event: Event, user: User, data: CampaignCreate
) -> PromotionalCampaign:
    if event.status in (EventStatus.CANCELLED, EventStatus.COMPLETED):
        raise AppError(409, "event_read_only", "Cancelled and completed events can't change.")
    if data.ticket_type_ids:
        found = set(
            await session.scalars(
                select(TicketType.id).where(
                    TicketType.event_id == event.id, TicketType.id.in_(data.ticket_type_ids)
                )
            )
        )
        if found != set(data.ticket_type_ids):
            raise AppError(404, "ticket_type_not_found", "Ticket type not found.")
    if data.code is not None:
        text = data.code
        if await _code_taken(session, text):
            raise AppError(409, "promo_code_taken", "That code is already in use. Pick another.")
    else:
        text = _new_code()
        while await _code_taken(session, text):
            text = _new_code()

    # Like event times, a date without a UTC offset is local time at the event.
    tz = ZoneInfo(event.timezone)
    starts_at = localize(data.starts_at, tz) if data.starts_at else None
    ends_at = localize(data.ends_at, tz) if data.ends_at else None
    if starts_at and ends_at and ends_at < starts_at:
        raise AppError(422, "invalid_window", "ends_at must not be before starts_at.")
    campaign = PromotionalCampaign(
        id=uuid.uuid4(),
        event_id=event.id,
        name=data.name,
        description=data.description,
        status=CampaignStatus.ACTIVE,
        discount_type=data.discount_type,
        discount_percent=data.discount_percent,
        discount_kzt=data.discount_kzt,
        starts_at=starts_at,
        ends_at=ends_at,
        qr_token=_new_token(),
        created_by_user_id=user.id,
    )
    session.add(campaign)
    await session.flush()
    code = PromoCode(
        id=uuid.uuid4(),
        campaign_id=campaign.id,
        code=text,
        max_redemptions=data.max_redemptions,
        is_active=True,
    )
    session.add(code)
    await session.flush()
    for tt_id in sorted(set(data.ticket_type_ids)):
        session.add(PromoCodeTicketType(promo_code_id=code.id, ticket_type_id=tt_id))
    worth = (
        f"{data.discount_percent}%"
        if data.discount_type is DiscountType.PERCENTAGE
        else f"{data.discount_kzt} KZT"
    )
    audit.record(
        session,
        actor_id=user.id,
        action="promo.created",
        entity_type="promotional_campaign",
        entity_id=campaign.id,
        description=f"Created campaign '{campaign.name}' with code {text} ({worth} off).",
        event_id=event.id,
    )
    try:
        await session.commit()
    except IntegrityError as exc:  # a concurrent create took the same code
        await session.rollback()
        raise AppError(409, "promo_code_taken", "That code is already in use.") from exc
    return campaign


async def update_campaign(
    session: AsyncSession,
    event: Event,
    campaign: PromotionalCampaign,
    user: User,
    data: CampaignUpdate,
) -> PromotionalCampaign:
    changes = data.model_dump(exclude_unset=True)
    code = await session.scalar(select(PromoCode).where(PromoCode.campaign_id == campaign.id))
    assert code is not None
    if "max_redemptions" in changes:
        limit = changes.pop("max_redemptions")
        if limit is not None and limit < code.redeemed_count:
            raise AppError(
                409,
                "max_redemptions_below_used",
                f"{code.redeemed_count} redemptions are already taken.",
            )
        code.max_redemptions = limit
    tz = ZoneInfo(event.timezone)
    for field in ("name", "description", "starts_at", "ends_at"):
        if field in changes:
            value = changes[field]
            if field == "name" and value is None:
                continue
            if field in ("starts_at", "ends_at") and value is not None:
                value = localize(value, tz)
            setattr(campaign, field, value)
    if campaign.starts_at and campaign.ends_at and campaign.ends_at < campaign.starts_at:
        raise AppError(422, "invalid_window", "ends_at must not be before starts_at.")
    audit.record(
        session,
        actor_id=user.id,
        action="promo.updated",
        entity_type="promotional_campaign",
        entity_id=campaign.id,
        description=(
            f"Updated campaign '{campaign.name}': {', '.join(sorted(data.model_fields_set))}."
        ),
        event_id=event.id,
    )
    await session.commit()
    return campaign


async def disable(
    session: AsyncSession, event: Event, campaign: PromotionalCampaign, user: User
) -> PromotionalCampaign:
    """SRS 4.16 lists promo-code disabling on the timeline. Orders already placed keep their
    discount; new checkouts are rejected with `promo_disabled`."""
    if campaign.status is not CampaignStatus.DISABLED:
        campaign.status = CampaignStatus.DISABLED
        campaign.disabled_at = datetime.now(UTC)
        await session.execute(
            update(PromoCode).where(PromoCode.campaign_id == campaign.id).values(is_active=False)
        )
        audit.record(
            session,
            actor_id=user.id,
            action="promo.disabled",
            entity_type="promotional_campaign",
            entity_id=campaign.id,
            description=f"Disabled campaign '{campaign.name}'.",
            event_id=event.id,
        )
        await session.commit()
    return campaign
