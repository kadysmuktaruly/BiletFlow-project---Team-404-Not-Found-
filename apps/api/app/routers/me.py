"""/me: the signed-in user's own account."""

from fastapi import APIRouter

from app.deps import CurrentUser, SessionDep
from app.errors import error_responses
from app.models import User
from app.schemas.user import UserRead, UserUpdate

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
