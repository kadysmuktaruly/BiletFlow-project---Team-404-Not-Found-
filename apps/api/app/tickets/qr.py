"""QR images for admission tokens (SRS 4.7: scannable from paper, including grayscale).

Error correction M and a 4-module quiet zone, pure black on white. The token is short, so
the symbol is small (version 3 or so) and each module stays large at any print size.
"""

import io

import segno


def qr_svg(payload: str, scale: int = 8) -> str:
    buffer = io.BytesIO()
    segno.make(payload, error="m", micro=False).save(
        buffer, kind="svg", scale=scale, border=4, dark="#000000", light="#ffffff", xmldecl=False
    )
    return buffer.getvalue().decode()


def qr_png(payload: str, scale: int = 8) -> bytes:
    buffer = io.BytesIO()
    segno.make(payload, error="m", micro=False).save(
        buffer, kind="png", scale=scale, border=4, dark="#000000", light="#ffffff"
    )
    return buffer.getvalue()
