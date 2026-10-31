"""Signed admission tokens: the payload of every ticket QR code (SRS 4.7, 4.8, 4.14).

Format::

    BFT1.<ticket id, 22 chars base64url>.<HMAC-SHA256 over "BFT1.<id>", first 16 bytes, base64url>

About 50 characters, so it fits `tickets.admission_token` (String(64), unique) and makes a
small, sparse QR code that still scans from a grayscale print.

* **Tamper-resistant.** Changing any character breaks the HMAC, and only the server holds
  `TICKET_SIGNING_SECRET`. A forged or edited code is rejected before any database lookup.
* **Identity only.** The token names a ticket and nothing else: no status, no price. Check-in
  always reads the ticket's live status, so a refunded ticket's old QR code stops working.
* **Disjoint from Campaign QR codes.** Campaign tokens start with `BFC1.` (see
  `app.models.campaign`). `parse_admission_token` accepts only `BFT1.`, so a promo code can
  never be read as permission to enter.
"""

import base64
import hashlib
import hmac
import uuid

from app.config import get_settings

ADMISSION_PREFIX = "BFT1."
_MAC_BYTES = 16  # 128-bit truncated HMAC-SHA256


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(body: str) -> bytes:
    key = get_settings().ticket_signing_secret.encode()
    return hmac.new(key, body.encode(), hashlib.sha256).digest()[:_MAC_BYTES]


def sign_admission_token(ticket_id: uuid.UUID) -> str:
    body = ADMISSION_PREFIX + _b64(ticket_id.bytes)
    return f"{body}.{_b64(_mac(body))}"


def parse_admission_token(payload: str) -> uuid.UUID | None:
    """The ticket id if `payload` is an authentic admission token, else None."""
    payload = payload.strip()
    if not payload.startswith(ADMISSION_PREFIX) or len(payload) > 64:
        return None
    body, _, mac = payload.rpartition(".")
    try:
        if not hmac.compare_digest(_unb64(mac), _mac(body)):
            return None
        return uuid.UUID(bytes=_unb64(body[len(ADMISSION_PREFIX) :]))
    except (ValueError, TypeError):
        return None
