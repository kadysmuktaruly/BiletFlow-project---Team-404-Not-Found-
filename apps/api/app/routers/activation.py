"""/organizer/events/{event_id}/activation: the paid-sales checklist (SRS 3.2, 4.5). DEMO."""

from fastapi import APIRouter

from app.deps import OrganizerUser, OwnedEvent, SessionDep
from app.errors import error_responses
from app.schemas.payment import (
    ActivationRead,
    ConfirmRequest,
    IdempotencyKey,
    SimulatedPaymentRequest,
)
from app.services import activation as activation_service

router = APIRouter(
    prefix="/organizer/events/{event_id}/activation",
    tags=["activation"],
    responses=error_responses(401, 403, 404),
)


@router.get(
    "",
    response_model=ActivationRead,
    summary="The event's paid-sales checklist",
    description=(
        "Paid checkout opens only when every step is done: a paid ticket type, the simulated "
        "identity check, a connected payout account, the DEMO activation fee and the terms."
    ),
)
async def read_checklist(
    event: OwnedEvent, user: OrganizerUser, session: SessionDep
) -> ActivationRead:
    return await activation_service.checklist(session, event, user)


@router.post(
    "/identity",
    response_model=ActivationRead,
    summary="Complete the simulated identity check (DEMO; no documents are collected)",
)
async def verify_identity(
    _: ConfirmRequest, event: OwnedEvent, user: OrganizerUser, session: SessionDep
) -> ActivationRead:
    return await activation_service.verify_identity(session, event, user)


@router.post(
    "/payout-account",
    response_model=ActivationRead,
    responses=error_responses(409),
    summary="Connect your simulated payout account to this event",
)
async def connect_payout_account(
    _: ConfirmRequest, event: OwnedEvent, user: OrganizerUser, session: SessionDep
) -> ActivationRead:
    return await activation_service.connect_payout_account(session, event, user)


@router.post(
    "/terms",
    response_model=ActivationRead,
    summary="Accept the paid-event terms",
)
async def accept_terms(
    _: ConfirmRequest, event: OwnedEvent, user: OrganizerUser, session: SessionDep
) -> ActivationRead:
    return await activation_service.accept_terms(session, event, user)


@router.post(
    "/fee-payment",
    response_model=ActivationRead,
    responses=error_responses(409, 422),
    summary="Pay the activation fee through the DEMO payment simulation",
    description=(
        "**DEMO: no real money moves.** Charges `ACTIVATION_FEE_KZT` once per event; the fee "
        "is non-refundable. Uses the same `Idempotency-Key` rules as ticket payments."
    ),
)
async def pay_fee(
    data: SimulatedPaymentRequest,
    idempotency_key: IdempotencyKey,
    event: OwnedEvent,
    user: OrganizerUser,
    session: SessionDep,
) -> ActivationRead:
    return await activation_service.pay_fee(session, event, user, idempotency_key, data.outcome)
