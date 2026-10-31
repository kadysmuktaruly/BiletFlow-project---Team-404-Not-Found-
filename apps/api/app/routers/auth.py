"""/auth: register, verify email, sign in and out, refresh, reset password (SRS 4.1)."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, Header, Response, status

from app.config import get_settings
from app.deps import SessionDep
from app.errors import AppError, error_responses
from app.models import User
from app.schemas.auth import (
    AcceptedResponse,
    EmailRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.user import UserRead
from app.services import auth as auth_service
from app.services.mail import Outbound, deliver

router = APIRouter(prefix="/auth", tags=["auth"])

# The scanner cannot hold an httpOnly cookie; it identifies itself with this header and
# receives the refresh token in the response body instead.
SCANNER_CLIENT = "scanner"
# Scoped to /api/v1/auth, so the refresh token only travels to refresh and logout.
REFRESH_COOKIE = "bf_refresh"
COOKIE_PATH = "/api/v1/auth"


def _schedule(background: BackgroundTasks, outbound: Outbound) -> None:
    for msg, notification_id in outbound:
        background.add_task(deliver, msg, notification_id)


def _session_response(user: User, response: Response, x_client: str | None) -> TokenResponse:
    settings = get_settings()
    access, refresh = auth_service.issue_tokens(user)
    body = TokenResponse(
        access_token=access,
        expires_in=settings.jwt_access_ttl_seconds,
        user=UserRead.model_validate(user),
    )
    if x_client == SCANNER_CLIENT:
        body.refresh_token = refresh
    else:
        response.set_cookie(
            REFRESH_COOKIE,
            refresh,
            max_age=settings.jwt_refresh_ttl_seconds,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            path=COOKIE_PATH,
        )
    return body


@router.post(
    "/register",
    response_model=AcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create an account and send a verification email",
    description="Responds identically whether or not the email is already registered.",
)
async def register(
    data: RegisterRequest, session: SessionDep, background: BackgroundTasks
) -> AcceptedResponse:
    _schedule(background, await auth_service.register(session, data))
    return AcceptedResponse()


@router.post(
    "/verify-email",
    response_model=UserRead,
    responses=error_responses(400),
    summary="Confirm an email address with the token from the verification email",
)
async def verify_email(data: VerifyEmailRequest, session: SessionDep) -> User:
    return await auth_service.verify_email(session, data.token)


@router.post(
    "/resend-verification",
    response_model=AcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send the verification email again",
)
async def resend_verification(
    data: EmailRequest, session: SessionDep, background: BackgroundTasks
) -> AcceptedResponse:
    _schedule(background, await auth_service.resend_verification(session, data.email))
    return AcceptedResponse()


@router.post(
    "/login",
    response_model=TokenResponse,
    responses=error_responses(401, 403),
    summary="Sign in",
    description=(
        "Returns an access token. Browsers get the refresh token as an httpOnly cookie; "
        "clients sending `X-Client: scanner` get it in the body."
    ),
)
async def login(
    data: LoginRequest,
    session: SessionDep,
    response: Response,
    x_client: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    user = await auth_service.authenticate(session, data.email, data.password)
    return _session_response(user, response, x_client)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses=error_responses(401),
    summary="Exchange a refresh token (cookie or body) for a new access token",
)
async def refresh(
    session: SessionDep,
    response: Response,
    data: RefreshRequest | None = None,
    x_client: Annotated[str | None, Header()] = None,
    cookie_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> TokenResponse:
    token = (data.refresh_token if data else None) or cookie_token
    if not token:
        raise AppError(401, "unauthorized", "Sign in to continue.")
    user = await auth_service.user_from_refresh_token(session, token)
    return _session_response(user, response, x_client)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sign out")
async def logout(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        REFRESH_COOKIE,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


@router.post(
    "/forgot-password",
    response_model=AcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Email a password-reset link",
    description="Responds identically whether or not the email is registered.",
)
async def forgot_password(
    data: EmailRequest, session: SessionDep, background: BackgroundTasks
) -> AcceptedResponse:
    _schedule(background, await auth_service.forgot_password(session, data.email))
    return AcceptedResponse()


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(400),
    summary="Set a new password with the token from the reset email",
    description="The link works once. Resetting also signs out every other session.",
)
async def reset_password(data: ResetPasswordRequest, session: SessionDep) -> None:
    await auth_service.reset_password(session, data.token, data.new_password)
