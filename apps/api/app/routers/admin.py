"""/admin: the Platform Admin portal (SRS 4.12). Platform Admins only (403 for everyone else);
every change is written to the audit log."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.deps import PlatformAdminUser, SessionDep
from app.enums import (
    ActivationStatus,
    EventReportStatus,
    EventStatus,
    OrderStatus,
    PaymentStatus,
    UserRole,
)
from app.errors import error_responses
from app.schemas.admin import (
    AdminActivation,
    AdminActivationList,
    AdminEvent,
    AdminEventList,
    AdminOrderList,
    AdminPaymentList,
    AdminReport,
    AdminReportList,
    AdminSummary,
    AdminUser,
    AdminUserList,
    ReportReview,
    SettingsRead,
    SettingsUpdate,
    SuspendRequest,
)
from app.services import admin as admin_service

router = APIRouter(prefix="/admin", tags=["admin"], responses=error_responses(401, 403))
Search = Annotated[str | None, Query(max_length=200)]


@router.get("/summary", response_model=AdminSummary, summary="Platform counts for the overview")
async def summary(_: PlatformAdminUser, session: SessionDep) -> AdminSummary:
    return await admin_service.summary(session)


# --- users ----------------------------------------------------------------------------------


@router.get("/users", response_model=AdminUserList, summary="Search users by email or name")
async def users(
    _: PlatformAdminUser,
    session: SessionDep,
    q: Search = None,
    role: UserRole | None = None,
    suspended: bool | None = None,
) -> AdminUserList:
    return await admin_service.list_users(session, q, role, suspended)


@router.post(
    "/users/{user_id}/suspend",
    response_model=AdminUser,
    responses=error_responses(404, 409, 422),
    summary="Suspend a user",
    description="They can't sign in, and their open sessions stop working at once.",
)
async def suspend_user(
    user_id: uuid.UUID, data: SuspendRequest, admin: PlatformAdminUser, session: SessionDep
) -> AdminUser:
    return await admin_service.set_user_suspended(session, admin, user_id, True, data.reason)


@router.post(
    "/users/{user_id}/unsuspend",
    response_model=AdminUser,
    responses=error_responses(404, 409),
    summary="Reinstate a user",
)
async def unsuspend_user(
    user_id: uuid.UUID, admin: PlatformAdminUser, session: SessionDep
) -> AdminUser:
    return await admin_service.set_user_suspended(session, admin, user_id, False, None)


# --- events, paid sales and activations ----------------------------------------------------


@router.get("/events", response_model=AdminEventList, summary="Search events")
async def events(
    _: PlatformAdminUser,
    session: SessionDep,
    q: Search = None,
    status: EventStatus | None = None,
    suspended: bool | None = None,
) -> AdminEventList:
    return await admin_service.list_events(session, q, status, suspended)


@router.post(
    "/events/{event_id}/suspend",
    response_model=AdminEvent,
    responses=error_responses(404, 422),
    summary="Suspend an event: stop all sales and hide it",
    description="Checkout stops on the next request; issued tickets stay valid.",
)
async def suspend_event(
    event_id: uuid.UUID, data: SuspendRequest, admin: PlatformAdminUser, session: SessionDep
) -> AdminEvent:
    return await admin_service.set_event_suspended(session, admin, event_id, True, data.reason)


@router.post(
    "/events/{event_id}/unsuspend",
    response_model=AdminEvent,
    responses=error_responses(404),
    summary="Reinstate an event",
)
async def unsuspend_event(
    event_id: uuid.UUID, admin: PlatformAdminUser, session: SessionDep
) -> AdminEvent:
    return await admin_service.set_event_suspended(session, admin, event_id, False, None)


@router.post(
    "/events/{event_id}/paid-sales/suspend",
    response_model=AdminActivation,
    responses=error_responses(404, 422),
    summary="Suspend paid sales for an event (fraud suspected)",
    description="Paid checkout and payment stop on the next request. Free tickets still work.",
)
async def suspend_paid_sales(
    event_id: uuid.UUID, data: SuspendRequest, admin: PlatformAdminUser, session: SessionDep
) -> AdminActivation:
    return await admin_service.set_paid_sales_suspended(session, admin, event_id, True, data.reason)


@router.post(
    "/events/{event_id}/paid-sales/resume",
    response_model=AdminActivation,
    responses=error_responses(404),
    summary="Resume paid sales",
    description="Active again if the checklist is complete, otherwise back to in progress.",
)
async def resume_paid_sales(
    event_id: uuid.UUID, admin: PlatformAdminUser, session: SessionDep
) -> AdminActivation:
    return await admin_service.set_paid_sales_suspended(session, admin, event_id, False, None)


@router.get(
    "/activations", response_model=AdminActivationList, summary="Paid-sales activation records"
)
async def activations(
    _: PlatformAdminUser,
    session: SessionDep,
    q: Search = None,
    status: ActivationStatus | None = None,
) -> AdminActivationList:
    return await admin_service.list_activations(session, q, status)


# --- orders and payments ------------------------------------------------------------------


@router.get("/orders", response_model=AdminOrderList, summary="Search orders")
async def orders(
    _: PlatformAdminUser, session: SessionDep, q: Search = None, status: OrderStatus | None = None
) -> AdminOrderList:
    return await admin_service.list_orders(session, q, status)


@router.get(
    "/payments",
    response_model=AdminPaymentList,
    summary="Search DEMO payments (failures, refunds…)",
)
async def payments(
    _: PlatformAdminUser,
    session: SessionDep,
    q: Search = None,
    status: PaymentStatus | None = None,
) -> AdminPaymentList:
    return await admin_service.list_payments(session, q, status)


# --- reports and settings -------------------------------------------------------------------


@router.get("/reports", response_model=AdminReportList, summary="Reported events")
async def reports(
    _: PlatformAdminUser, session: SessionDep, status: EventReportStatus | None = None
) -> AdminReportList:
    return await admin_service.list_reports(session, status)


@router.post(
    "/reports/{report_id}/review",
    response_model=AdminReport,
    responses=error_responses(404, 409, 422),
    summary="Dismiss a report, or suspend the reported event",
)
async def review_report(
    report_id: uuid.UUID, data: ReportReview, admin: PlatformAdminUser, session: SessionDep
) -> AdminReport:
    return await admin_service.review_report(session, admin, report_id, data)


@router.get("/settings", response_model=SettingsRead, summary="Platform settings")
async def read_settings(_: PlatformAdminUser, session: SessionDep) -> SettingsRead:
    return await admin_service.read_settings(session)


@router.put(
    "/settings",
    response_model=SettingsRead,
    responses=error_responses(422),
    summary="Change platform settings (the activation fee)",
    description="The new fee applies to activation fees paid from now on.",
)
async def update_settings(
    data: SettingsUpdate, admin: PlatformAdminUser, session: SessionDep
) -> SettingsRead:
    return await admin_service.update_settings(session, admin, data)


@router.get(
    "/export/{kind}.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}, **error_responses(422)},
    summary="Download users, events, orders or payments as CSV",
    description="Up to 10,000 rows, newest first. Payments are DEMO records.",
)
async def export(
    kind: Literal["users", "events", "orders", "payments"],
    admin: PlatformAdminUser,
    session: SessionDep,
) -> Response:
    body = await admin_service.export_csv(session, admin, kind)
    return Response(
        body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="biletflow-{kind}.csv"'},
    )
