"""/me: the signed-in user's own account."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import Response

from app import ratelimit
from app.deps import CurrentUser, SessionDep
from app.errors import error_responses
from app.i18n import normalize_locale
from app.models import User
from app.routers.auth import clear_refresh_cookie
from app.schemas.notification import NotificationList, NotificationRead, UnreadCount
from app.schemas.order import MyTicketRead, OrderRead
from app.schemas.user import AccountDeleteRequest, UserRead, UserUpdate
from app.services import account as account_service
from app.services import notifications as notification_service
from app.services import orders as order_service
from app.tickets.pdf import render_ticket_pdf
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


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(400, 409, 429),
    summary="Delete your account",
    description=(
        "Needs the current password. The account is anonymised rather than removed: name, "
        "email, phone and password are replaced, every session ends, and the email can be "
        "registered again. Orders and tickets stay as the record of sales. "
        "Platform Admins can't delete their account here (409 `cannot_delete_admin`), and "
        "organizers must first cancel or finish their published events "
        "(409 `organizer_has_live_events`). A wrong password is 400 `invalid_password`."
    ),
)
async def delete_me(
    data: AccountDeleteRequest,
    user: CurrentUser,
    session: SessionDep,
    request: Request,
    response: Response,
) -> None:
    ratelimit.enforce(request, "delete-account", user.email)
    await account_service.delete_account(session, user, data.password)
    clear_refresh_cookie(response)


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


@router.get(
    "/tickets/{ticket_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}, **error_responses(404)},
    summary="The ticket as a print-optimized A4 PDF",
    description=(
        "SRS 4.7: event, date and time, venue, ticket type, attendee, seat when assigned, "
        "ticket number and the same QR as the digital ticket. No price or payment data. "
        "Text is in your account language."
    ),
)
async def my_ticket_pdf(ticket_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    ticket = await order_service.get_own_ticket(session, user, ticket_id)
    (document,) = await order_service.ticket_documents(session, [ticket])
    pdf = render_ticket_pdf(document, normalize_locale(user.locale), datetime.now(UTC))
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ticket-{ticket.ticket_number}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )


# --- in-app notifications (SRS 4.10, 4.13) ------------------------------------------------


@router.get(
    "/notifications",
    response_model=NotificationList,
    summary="Your in-app notifications, newest first",
    description="Every notification is also emailed. `unread_count` counts all unread items.",
)
async def my_notifications(
    user: CurrentUser,
    session: SessionDep,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> NotificationList:
    items, unread = await notification_service.list_in_app(
        session, user, unread_only=unread_only, limit=limit
    )
    return NotificationList(
        items=[NotificationRead.model_validate(n) for n in items], unread_count=unread
    )


@router.get(
    "/notifications/unread-count",
    response_model=UnreadCount,
    summary="How many in-app notifications are unread (for the header badge)",
)
async def my_unread_count(user: CurrentUser, session: SessionDep) -> UnreadCount:
    return UnreadCount(unread_count=await notification_service.unread_count(session, user))


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationRead,
    responses=error_responses(404),
    summary="Mark one notification as read",
)
async def read_notification(
    notification_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> NotificationRead:
    notification = await notification_service.mark_read(session, user, notification_id)
    return NotificationRead.model_validate(notification)


@router.post(
    "/notifications/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark every notification as read",
)
async def read_all_notifications(user: CurrentUser, session: SessionDep) -> Response:
    await notification_service.mark_all_read(session, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
