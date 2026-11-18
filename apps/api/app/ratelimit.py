"""Rate limiting for sign-in and account emails (Report 6 hardening).

A sliding window per (rule, key) kept in this process's memory. The API runs as a single
uvicorn process (see apps/api/Dockerfile), so that is exact; running several workers would
need shared state (e.g. a Postgres table) instead.

Keys are the client IP and, where the request names an account, the email (lower-cased).
The email limit counts every attempt for that address whether or not it's registered, so a
429 never reveals that an account exists (CLAUDE.md).
"""

import hmac
import time
from collections import deque
from dataclasses import dataclass

from fastapi import Request

from app.config import get_settings
from app.errors import AppError


@dataclass(frozen=True)
class Rule:
    limit: int
    window_seconds: int


# Generous for people, tight for scripts.
RULES: dict[str, Rule] = {
    "login:ip": Rule(20, 60),
    "login:email": Rule(5, 60),
    "register:ip": Rule(5, 600),
    "account-email:ip": Rule(5, 900),
    "account-email:email": Rule(3, 900),
}

_hits: dict[tuple[str, str], deque[float]] = {}


def reset() -> None:
    _hits.clear()


def enabled() -> bool:
    settings = get_settings()
    if settings.rate_limit_enabled is not None:
        return settings.rate_limit_enabled
    return settings.environment != "test"


def _hit(rule_name: str, key: str, now: float) -> int | None:
    """Record an attempt. Seconds to wait if it's over the limit, else None."""
    rule = RULES[rule_name]
    window = _hits.setdefault((rule_name, key), deque())
    while window and window[0] <= now - rule.window_seconds:
        window.popleft()
    if len(window) >= rule.limit:
        return int(window[0] + rule.window_seconds - now) + 1
    window.append(now)
    return None


# Set by the web app's same-origin proxy (apps/web/src/proxy.ts).
PROXY_SECRET_HEADER = "x-biletflow-proxy-secret"
PROXY_CLIENT_IP_HEADER = "x-biletflow-client-ip"


def client_ip(request: Request) -> str:
    """The visitor's address. Behind the web app's proxy every request comes from the proxy,
    so its forwarded address is used, but only when the shared secret proves the proxy sent it.
    """
    secret = get_settings().trusted_proxy_secret
    forwarded = request.headers.get(PROXY_CLIENT_IP_HEADER, "").strip()
    sent = request.headers.get(PROXY_SECRET_HEADER, "")
    if secret and forwarded and hmac.compare_digest(sent.encode(), secret.encode()):
        return forwarded
    return request.client.host if request.client else "unknown"


def enforce(request: Request, scope: str, email: str | None = None) -> None:
    """Raise 429 `rate_limited` (with Retry-After) when this client or address has made too
    many attempts. `scope` is `login`, `register` or `account-email`."""
    if not enabled():
        return
    now = time.monotonic()
    waits = [_hit(f"{scope}:ip", client_ip(request), now)]
    if email is not None and f"{scope}:email" in RULES:
        waits.append(_hit(f"{scope}:email", email.strip().lower(), now))
    wait = max((w for w in waits if w is not None), default=None)
    if wait is not None:
        raise AppError(
            429,
            "rate_limited",
            "Too many attempts. Please wait a little and try again.",
            details=None,
            headers={"Retry-After": str(wait)},
        )
