"""/me: the signed-in user's own account."""

import uuid

from fastapi import APIRouter
from fastapi.responses import Response

from app.deps import CurrentUser, SessionDep
from app.errors import error_responses
from app.models import User
from app.schemas.order import MyTicketRead, OrderRead
from app.schemas.user import UserRead, UserUpdate
from app.services import orders as order_service
from app.tickets.qr import qr_svg

router = APIRouter(prefix="/me", tags=["me"], responses=error_responses(401, 403))


@router.get("", response_model=UserRead, summary="The signed-in user")
async def read_me(user: CurrentUser) -> User:
    return user


@router.patch("", response_model=UserRead, summary="Update your name, phone or language")
async def update_me(data: UserUpdate, user: CurrentUser, session: SessionDep) -> User:
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None or field == "phone":
            setattr(user, field, value)
    await session.commit()
    return user


@router.get("/orders", response_model=list[OrderRead], summary="Your orders, newest first")
async def my_orders(user: CurrentUser, session: SessionDep) -> list[OrderRead]:
    return [
        await order_service.order_read(session, o)
        for o in await order_service.list_own_orders(session, user)
    ]


@router.get("/tickets", response_model=list[MyTicketRead], summary="Your tickets (SRS 4.7)")
async def my_tickets(user: CurrentUser, session: SessionDep) -> list[MyTicketRead]:
    return await order_service.list_own_tickets(session, user)


@router.get(
    "/tickets/{ticket_id}/qr.svg",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}}}, **error_responses(404)},
    summary="The ticket's admission QR code as SVG",
)
async def my_ticket_qr(ticket_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    ticket = await order_service.get_own_ticket(session, user, ticket_id)
    return Response(
        qr_svg(ticket.admission_token),
        media_type="image/svg+xml",
        headers={"Cache-Control": "private, no-store"},
    )
