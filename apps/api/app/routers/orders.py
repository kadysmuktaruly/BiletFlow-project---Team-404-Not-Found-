"""/orders: checkout (SRS 4.4, 4.6). Attendees must be signed in; there is no guest checkout."""

import uuid

from fastapi import APIRouter, status

from app.deps import CurrentUser, SessionDep
from app.errors import error_responses
from app.schemas.order import OrderCreate, OrderRead
from app.services import orders as order_service

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
async def create_order(data: OrderCreate, user: CurrentUser, session: SessionDep) -> OrderRead:
    order = await order_service.create_order(session, user, data)
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
