"""SRS 4.7: the admission QR token is tamper-resistant and identifies one ticket."""

import uuid

import pytest

from app.config import get_settings
from app.tickets.tokens import ADMISSION_PREFIX, parse_admission_token, sign_admission_token


@pytest.mark.parametrize("attempt", range(25))  # many random ids: trailing base64 bits vary
def test_admission_token_signature_and_tamper(attempt: int) -> None:
    ticket_id = uuid.uuid4()
    token = sign_admission_token(ticket_id)
    assert token.startswith(ADMISSION_PREFIX)
    assert len(token) <= 64  # fits tickets.admission_token
    assert parse_admission_token(token) == ticket_id
    assert parse_admission_token(f"  {token}\n") == ticket_id  # scanners may add whitespace

    for i in range(len(ADMISSION_PREFIX), len(token)):
        if token[i] == ".":
            continue
        for swapped in "ABQgw_-":  # covers chars that differ only in unused low bits
            if swapped != token[i]:
                assert parse_admission_token(token[:i] + swapped + token[i + 1 :]) is None, i


def test_another_tickets_signature_does_not_transfer() -> None:
    a, b = sign_admission_token(uuid.uuid4()), sign_admission_token(uuid.uuid4())
    forged = a.rsplit(".", 1)[0] + "." + b.rsplit(".", 1)[1]
    assert parse_admission_token(forged) is None


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "BFT1.",
        "BFT1..",
        "BFC1.abcdefghijklmnopqrstuvwxyz",
        "https://biletflow.kz/c/BFC1.x",
        "x" * 500,
    ],
)
def test_garbage_and_campaign_payloads_are_not_admission_tokens(payload: str) -> None:
    assert parse_admission_token(payload) is None


def test_tokens_signed_with_another_secret_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    token = sign_admission_token(uuid.uuid4())
    monkeypatch.setattr(get_settings(), "ticket_signing_secret", "a-different-secret-" + "z" * 20)
    assert parse_admission_token(token) is None
