"""Email rendering and MIME assembly. Delivery to Mailpit is checked in the demo docs."""

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
