"""/orders: checkout (SRS 4.4, 4.6). Attendees must be signed in; there is no guest checkout."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Response, status

from app.deps import CurrentUser, SessionDep
from app.errors import error_responses
from app.schemas.order import OrderCreate, OrderRead
from app.schemas.payment import IdempotencyKey, OrderPaymentResult, SimulatedPaymentRequest
from app.services import orders as order_service
from app.services import payments as payment_service
from app.services.mail import schedule

router = APIRouter(prefix="/orders", tags=["orders"], responses=error_responses(401, 403))


@router.post(
    "",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(404, 409, 422),
    summary="Reserve tickets and create an order",
    description=(
        "Send ticket type ids and quantities only; the server computes every price. "
        "A zero-total order (free registration) is confirmed at once and its tickets issued. "
        "A paid order is `awaiting_payment` and holds its tickets until `expires_at`. "
        "`409 sold_out` when there aren't enough tickets left."
    ),
)
async def create_order(
    data: OrderCreate, user: CurrentUser, session: SessionDep, background: BackgroundTasks
) -> OrderRead:
    order, outbound = await order_service.create_order(session, user, data)
    schedule(background, outbound)
    return await order_service.order_read(session, order)


@router.get(
    "/{order_id}",
    response_model=OrderRead,
    responses=error_responses(404),
    summary="One of your orders",
)
async def read_order(order_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> OrderRead:
    order = await order_service.get_own_order(session, user, order_id)
    return await order_service.order_read(session, order)


@router.post(
    "/{order_id}/payments",
    response_model=OrderPaymentResult,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": OrderPaymentResult, "description": "Replay of an earlier attempt"},
        **error_responses(404, 409, 422),
    },
    summary="Pay for an order through the DEMO payment simulation",
    description=(
        "**DEMO: no real money moves.** `outcome` chooses what the simulated provider does. "
        "`succeed` confirms the order, issues the tickets and emails them. `fail` releases "
        "the tickets and emails a failure notice. Send a unique `Idempotency-Key` per "
        "attempt; repeating it returns the original result (200, `replayed: true`) instead "
        "of charging again. Reusing it for a different order is `409 idempotency_key_reused`."
    ),
)
async def pay_order(
    order_id: uuid.UUID,
    data: SimulatedPaymentRequest,
    idempotency_key: IdempotencyKey,
    user: CurrentUser,
    session: SessionDep,
    background: BackgroundTasks,
    response: Response,
) -> OrderPaymentResult:
    order, payment, replayed, outbound = await payment_service.pay_order(
        session, user, order_id, idempotency_key, data.outcome
    )
    schedule(background, outbound)
    if replayed:
        response.status_code = status.HTTP_200_OK
    return OrderPaymentResult(
        payment=payment_service.payment_read(payment),
        order=await order_service.order_read(session, order),
        replayed=replayed,
    )


@router.post(
    "/{order_id}/abandon",
    response_model=OrderRead,
    responses=error_responses(404, 409),
    summary="Leave the DEMO payment step and release the reserved tickets",
)
async def abandon_order(order_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> OrderRead:
    order = await payment_service.abandon_order(session, user, order_id)
    return await order_service.order_read(session, order)
