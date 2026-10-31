"""Password hashing and signed tokens (SRS 4.1, SRS 7).

Every token is a JWT signed with `JWT_SECRET` and carries a `typ` claim, so a token minted
for one purpose (say, an email-verification link) can never be replayed as another (an
access token). `decode_token` checks `typ` before anything else trusts the claims.

Refresh and password-reset tokens also carry `pwd`: a short fingerprint of the user's
current password hash. Changing the password changes the fingerprint, which makes every
outstanding reset link single-use and signs the user out of every other session, without
a token table.
"""

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings
from app.errors import AppError

_hasher = PasswordHasher()
_ALGORITHM = "HS256"

# A real Argon2 hash of a random value. Verifying against it when an email is unknown keeps
# a failed login as slow as a wrong password, so timing does not reveal registered emails.
_DUMMY_HASH = _hasher.hash(uuid.uuid4().hex)


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"


async def hash_password(password: str) -> str:
    # Argon2 is deliberately CPU-heavy; keep it off the event loop.
    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password: str, hashed: str | None) -> bool:
    def _verify() -> bool:
        try:
            return _hasher.verify(hashed or _DUMMY_HASH, password)
        except (VerificationError, InvalidHashError):
            return False

    ok = await asyncio.to_thread(_verify)
    return ok and hashed is not None


def password_fingerprint(hashed_password: str) -> str:
    return hashlib.sha256(hashed_password.encode()).hexdigest()[:16]


def _ttl(token_type: TokenType) -> int:
    s = get_settings()
    return {
        TokenType.ACCESS: s.jwt_access_ttl_seconds,
        TokenType.REFRESH: s.jwt_refresh_ttl_seconds,
        TokenType.VERIFY_EMAIL: s.email_verify_ttl_seconds,
        TokenType.RESET_PASSWORD: s.password_reset_ttl_seconds,
    }[token_type]


def create_token(token_type: TokenType, user_id: uuid.UUID, **claims: Any) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "typ": token_type.value,
        "iat": now,
        "exp": now + timedelta(seconds=_ttl(token_type)),
        **claims,
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=_ALGORITHM)


def decode_token(token: str, expected: TokenType) -> dict[str, Any]:
    """Return the claims, or raise a 401 (access/refresh) or 400 (email links)."""
    link = expected in (TokenType.VERIFY_EMAIL, TokenType.RESET_PASSWORD)
    status, code = (400, "invalid_token") if link else (401, "unauthorized")
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[_ALGORITHM],
            options={"require": ["sub", "typ", "exp"]},
        )
        if claims["typ"] != expected.value:
            raise jwt.InvalidTokenError("wrong token type")
        uuid.UUID(claims["sub"])
    except jwt.ExpiredSignatureError as exc:
        raise AppError(status, "token_expired" if link else code, "The token has expired.") from exc
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise AppError(status, code, "The token is invalid.") from exc
    return claims
