"""/checkin: endpoints for the Event Admin scanner app (SRS 4.8)."""

from fastapi import APIRouter

from app.deps import CurrentUser, SessionDep
from app.errors import error_responses
from app.schemas.checkin import CheckInEvent
from app.services import checkin as checkin_service

router = APIRouter(prefix="/checkin", tags=["check-in"], responses=error_responses(401, 403))


@router.get(
    "/events",
    response_model=list[CheckInEvent],
    summary="Events you can check attendees in at",
    description=(
        "Only events you organize or are assigned to as staff (SRS 4.8: 'view only assigned "
        "events'), while published or unpublished and until a day after they end."
    ),
)
async def list_events(user: CurrentUser, session: SessionDep) -> list[CheckInEvent]:
    return await checkin_service.list_events(session, user)
