"""Requests and responses for /auth (SRS 4.1)."""

from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field

from app.i18n import Locale
from app.schemas.user import UserRead

# SRS 7 asks for secure hashing; a floor on length is the one rule worth enforcing here.
Password = Annotated[str, Field(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    full_name: str = Field(min_length=1, max_length=200)
    # Self-registration may pick only these two. `platform_admin` is never self-assignable,
    # and event admins are granted per event through StaffAssignment.
    role: Literal["attendee", "organizer"] = "attendee"
    locale: Locale = "kk"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """The scanner app sends its refresh token in the body; the web app uses the cookie."""

    refresh_token: str | None = None


class EmailRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: Password


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserRead
    # Only for clients that sent `X-Client: scanner`. Browsers get an httpOnly cookie instead.
    refresh_token: str | None = None


class VerifyEmailResponse(BaseModel):
    user: UserRead
    # Set only when this request confirmed the address: the user is signed in. A link that was
    # already used returns null here, and the user signs in with their password.
    session: TokenResponse | None = None


class AcceptedResponse(BaseModel):
    """Returned by resend-verification and forgot-password whatever the email, so the
    response never reveals whether an account exists. Register returns it for a new account
    (a taken email gets 409 `email_taken`)."""

    status: Literal["accepted"] = "accepted"
