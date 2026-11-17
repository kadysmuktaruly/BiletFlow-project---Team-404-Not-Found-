"""/support: support cases (SRS 4.13). A case you may not see returns 404."""

import uuid

from fastapi import APIRouter, BackgroundTasks, status

from app.deps import CurrentUser, SessionDep
from app.errors import error_responses
from app.schemas.support import CaseCreate, CaseRead, CaseSummary, CaseUpdate, MessageCreate
from app.services import support as support_service
from app.services.mail import schedule

router = APIRouter(prefix="/support", tags=["support"], responses=error_responses(401, 403))


@router.post(
    "/cases",
    response_model=CaseRead,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(404, 422),
    summary="Open a support case",
    description=(
        "`attendee` cases come from an event, order or ticket page and go to the event's "
        "organizer team; the event is derived from the order or ticket, which must be yours. "
        "`organizer` cases go to the platform (organizers only). No attachments."
    ),
)
async def open_case(
    data: CaseCreate, user: CurrentUser, session: SessionDep, background: BackgroundTasks
) -> CaseRead:
    case, outbound = await support_service.create_case(session, user, data)
    schedule(background, outbound)
    return await support_service.read_case(session, user, case.id)


@router.get(
    "/cases",
    response_model=list[CaseSummary],
    summary="Cases you opened and cases you handle",
    description="Most recently active first. Poll it; there are no sockets (SRS 4.13).",
)
async def list_cases(user: CurrentUser, session: SessionDep) -> list[CaseSummary]:
    return await support_service.list_cases(session, user)


@router.get(
    "/cases/{case_id}",
    response_model=CaseRead,
    responses=error_responses(404),
    summary="A case with its message thread",
    description="Requesters never see internal notes. Poll this to refresh the thread.",
)
async def read_case(case_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> CaseRead:
    return await support_service.read_case(session, user, case_id)


@router.post(
    "/cases/{case_id}/messages",
    response_model=CaseRead,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(404, 422),
    summary="Reply in a case",
    description=(
        "A requester's reply moves a case that was waiting for them back to In progress, and "
        "a resolved case back to Open. `internal: true` (staff only) adds a note the "
        "requester never sees."
    ),
)
async def reply(
    case_id: uuid.UUID,
    data: MessageCreate,
    user: CurrentUser,
    session: SessionDep,
    background: BackgroundTasks,
) -> CaseRead:
    case, outbound = await support_service.add_message(session, user, case_id, data)
    schedule(background, outbound)
    return await support_service.read_case(session, user, case.id)


@router.patch(
    "/cases/{case_id}",
    response_model=CaseRead,
    responses=error_responses(404, 422),
    summary="Change a case's status or assignee (handling staff only)",
    description=(
        "Statuses: open, in_progress, waiting_for_customer, resolved. Assign to someone from "
        "the case's `assignees`, or null to unassign. The requester is notified of status "
        "changes, and the assignee of the assignment."
    ),
)
async def update_case(
    case_id: uuid.UUID,
    data: CaseUpdate,
    user: CurrentUser,
    session: SessionDep,
    background: BackgroundTasks,
) -> CaseRead:
    case, outbound = await support_service.update_case(session, user, case_id, data)
    schedule(background, outbound)
    return await support_service.read_case(session, user, case.id)
