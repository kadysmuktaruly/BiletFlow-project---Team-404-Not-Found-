"""Email rendering and MIME assembly. Delivery to Mailpit is checked in the demo docs."""

from typing import Any

import aiosmtplib
import pytest

from app.config import get_settings
from app.services import mail
from app.services.mail import Attachment, _to_mime, render


def test_render_escapes_user_input_in_html_but_not_text() -> None:
    msg = render(
        "verify_email",
        "en",
        to="a@example.com",
        action_url="http://localhost:3000/en/verify-email?token=abc",
        name="<script>alert(1)</script>",
        hours=24,
    )
    assert "<script>" not in msg.html
    assert "&lt;script&gt;" in msg.html
    assert "Hello <script>alert(1)</script>," in msg.text
    assert "expires in 24 hours" in msg.text


def test_unknown_locale_falls_back_to_kazakh() -> None:
    msg = render("verify_email", "de", to="a@example.com", name="A", hours=24)
    assert msg.subject == "BiletFlow электрондық поштаңызды растаңыз"


def test_mime_has_text_html_inline_image_and_attachment() -> None:
    msg = render("verify_email", "en", to="a@example.com", name="A", hours=24)
    msg.attachments = [
        Attachment("qr.png", b"\x89PNG fake", "image/png", inline_cid="qr-1"),
        Attachment("ticket.pdf", b"%PDF fake", "application/pdf"),
    ]
    mime = _to_mime(msg)
    types = [part.get_content_type() for part in mime.walk()]
    assert "text/plain" in types
    assert "text/html" in types
    assert "image/png" in types
    assert "application/pdf" in types
    inline = next(p for p in mime.walk() if p.get_content_type() == "image/png")
    assert inline["Content-ID"] == "<qr-1>"
    assert inline.get_content_disposition() == "inline"
    pdf = next(p for p in mime.walk() if p.get_content_type() == "application/pdf")
    assert pdf.get_content_disposition() == "attachment"


def _capture_send(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    async def fake_send(message: object, **kwargs: Any) -> None:
        seen.update(kwargs)

    monkeypatch.setattr(aiosmtplib, "send", fake_send)
    monkeypatch.setattr(get_settings(), "email_backend", "smtp")
    return seen


def _message() -> mail.OutgoingEmail:
    return mail.OutgoingEmail(to="a@example.com", subject="Hi", text="Hi", html="<p>Hi</p>")


async def test_smtp_defaults_send_without_login_for_mailpit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _capture_send(monkeypatch)
    await mail.send_email(_message())
    assert seen["username"] is None
    assert seen["password"] is None
    assert seen["use_tls"] is False
    assert seen["start_tls"] is None


async def test_smtp_login_and_starttls_for_a_real_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _capture_send(monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_username", "sender@example.com")
    monkeypatch.setattr(settings, "smtp_password", "app-password")
    monkeypatch.setattr(settings, "smtp_security", "starttls")
    await mail.send_email(_message())
    assert seen["username"] == "sender@example.com"
    assert seen["password"] == "app-password"
    assert seen["start_tls"] is True
    assert seen["use_tls"] is False


async def test_smtp_ssl_connects_over_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _capture_send(monkeypatch)
    monkeypatch.setattr(get_settings(), "smtp_security", "ssl")
    await mail.send_email(_message())
    assert seen["use_tls"] is True
    assert seen["start_tls"] is None
