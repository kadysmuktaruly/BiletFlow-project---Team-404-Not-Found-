"""Paid-sales activation (SRS 3.2, 4.5, UC2): a per-event checklist, all simulated.

Paid checkout stays closed until all five steps are done:

1. the event has at least one paid ticket type (derived, never set by hand),
2. identity check (a simulated confirmation; no documents are collected, SRS 8),
3. a payout account is connected (the organizer's simulated account),
4. the activation fee (`ACTIVATION_FEE_KZT`, non-refundable) is paid through the DEMO provider,
5. the paid-event terms are accepted.

Activation applies to that one event only. A Platform Admin suspension (`SUSPENDED`) closes
paid checkout again regardless of the checklist.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import ActivationStatus, PaymentPurpose, PaymentStatus, PayoutAccountStatus
from app.errors import AppError
from app.models import Event, PaidSalesActivation, Payment, TicketType, User
from app.schemas.payment import ActivationRead
from app.services import audit
from app.services.organizer import get_or_create_profile, get_payout_account
from app.services.payments import (
    Outcome,
    find_by_key,
    insert_payment,
    new_payment,
    payment_read,
    replay_or_conflict,
)


async def get_or_create(session: AsyncSession, event: Event) -> PaidSalesActivation:
    activation = await session.scalar(
        select(PaidSalesActivation).where(PaidSalesActivation.event_id == event.id)
    )
    if activation is None:
        activation = PaidSalesActivation(event_id=event.id, status=ActivationStatus.NOT_STARTED)
        session.add(activation)
        await session.flush()
    return activation


async def _has_paid_ticket_type(session: AsyncSession, event_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            select(exists().where(TicketType.event_id == event_id, TicketType.price_kzt > 0))
        )
    )


async def refresh_status(
    session: AsyncSession, activation: PaidSalesActivation, actor: User | None
) -> None:
    activation.has_paid_ticket_type = await _has_paid_ticket_type(session, activation.event_id)
    if activation.status is ActivationStatus.SUSPENDED:
        return
    steps = (
        activation.has_paid_ticket_type,
        activation.identity_verified,
        activation.payout_account_connected,
        activation.activation_fee_paid,
        activation.terms_accepted,
    )
    if all(steps):
        if activation.status is not ActivationStatus.ACTIVE:
            activation.status = ActivationStatus.ACTIVE
            activation.activated_at = datetime.now(UTC)
            audit.record(
                session,
                actor_id=actor.id if actor else None,
                action="activation.activated",
                entity_type="paid_sales_activation",
                entity_id=activation.id,
                description="Paid sales activated (DEMO)",
                event_id=activation.event_id,
            )
    elif any(steps[1:]):
        activation.status = ActivationStatus.IN_PROGRESS
    else:
        activation.status = ActivationStatus.NOT_STARTED


async def read(session: AsyncSession, activation: PaidSalesActivation) -> ActivationRead:
    payment = (
        await session.get(Payment, activation.activation_payment_id)
        if activation.activation_payment_id
        else None
    )
    return ActivationRead(
        event_id=activation.event_id,
        status=activation.status,
        paid_sales_enabled=activation.status is ActivationStatus.ACTIVE,
        has_paid_ticket_type=activation.has_paid_ticket_type,
        identity_verified=activation.identity_verified,
        payout_account_connected=activation.payout_account_connected,
        activation_fee_paid=activation.activation_fee_paid,
        terms_accepted=activation.terms_accepted,
        activation_fee_kzt=activation.activation_fee_kzt or get_settings().activation_fee_kzt,
        activation_payment=payment_read(payment) if payment else None,
        activated_at=activation.activated_at,
        suspended_at=activation.suspended_at,
    )


async def checklist(session: AsyncSession, event: Event, user: User) -> ActivationRead:
    activation = await get_or_create(session, event)
    await refresh_status(session, activation, user)
    await session.commit()
    return await read(session, activation)


def _log_step(
    session: AsyncSession, user: User, activation: PaidSalesActivation, step: str
) -> None:
    audit.record(
        session,
        actor_id=user.id,
        action=f"activation.{step}",
        entity_type="paid_sales_activation",
        entity_id=activation.id,
        description=f"Activation step completed: {step.replace('_', ' ')} (DEMO)",
        event_id=activation.event_id,
    )


async def verify_identity(session: AsyncSession, event: Event, user: User) -> ActivationRead:
    activation = await get_or_create(session, event)
    if not activation.identity_verified:
        activation.identity_verified = True
        _log_step(session, user, activation, "identity_verified")
    await refresh_status(session, activation, user)
    await session.commit()
    return await read(session, activation)


async def connect_payout_account(session: AsyncSession, event: Event, user: User) -> ActivationRead:
    profile = await get_or_create_profile(session, user)
    account = await get_payout_account(session, profile)
    if account is None or account.status is not PayoutAccountStatus.VERIFIED:
        raise AppError(
            409, "payout_account_required", "Set up your payout account in your profile first."
        )
    activation = await get_or_create(session, event)
    activation.payout_account_id = account.id
    if not activation.payout_account_connected:
        activation.payout_account_connected = True
        _log_step(session, user, activation, "payout_account_connected")
    await refresh_status(session, activation, user)
    await session.commit()
    return await read(session, activation)


async def accept_terms(session: AsyncSession, event: Event, user: User) -> ActivationRead:
    activation = await get_or_create(session, event)
    if not activation.terms_accepted:
        activation.terms_accepted = True
        _log_step(session, user, activation, "terms_accepted")
    await refresh_status(session, activation, user)
    await session.commit()
    return await read(session, activation)


async def pay_fee(
    session: AsyncSession, event: Event, user: User, key: str, outcome: Outcome
) -> ActivationRead:
    """The one-time activation fee through the DEMO provider, with the same idempotency rules
    as ticket payments. A failed attempt can be retried with a new key."""
    activation = await get_or_create(session, event)
    existing = await find_by_key(session, user, key)
    if existing is not None:
        replay_or_conflict(
            existing, PaymentPurpose.ACTIVATION_FEE, order_id=None, event_id=event.id
        )
        return await read(session, activation)
    # Lock first, then check: a concurrent attempt may have just paid.
    await session.refresh(activation, with_for_update=True)
    if activation.activation_fee_paid:
        raise AppError(409, "activation_fee_already_paid", "The activation fee is already paid.")
    fee = get_settings().activation_fee_kzt
    payment = new_payment(user, key, PaymentPurpose.ACTIVATION_FEE, fee, outcome, event_id=event.id)
    if not await insert_payment(session, payment):
        await session.rollback()
        return await read(session, await get_or_create(session, event))
    if payment.status is PaymentStatus.SUCCEEDED:
        activation.activation_fee_paid = True
        activation.activation_fee_kzt = fee
        activation.activation_payment_id = payment.id
    audit.record(
        session,
        actor_id=user.id,
        action="payment.succeeded"
        if payment.status is PaymentStatus.SUCCEEDED
        else "payment.failed",
        entity_type="payment",
        entity_id=payment.id,
        description=f"DEMO activation fee {fee} KZT ({payment.status.value})",
        event_id=event.id,
    )
    await refresh_status(session, activation, user)
    await session.commit()
    return await read(session, activation)


async def ensure_paid_sales_enabled(session: AsyncSession, event_id: uuid.UUID) -> None:
    """SRS 4.5: paid tickets can't be bought before activation, or while it's suspended."""
    status = await session.scalar(
        select(PaidSalesActivation.status).where(PaidSalesActivation.event_id == event_id)
    )
    if status is not ActivationStatus.ACTIVE:
        raise AppError(
            409, "paid_sales_not_active", "Paid tickets for this event aren't on sale yet."
        )
