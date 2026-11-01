"""Human-facing references: order references and ticket numbers.

Random, not sequential, so they reveal nothing about sales volume. The alphabet drops
0/O and 1/I/L so a reference read aloud to support staff is unambiguous.
"""

import secrets

_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def _code(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def order_reference() -> str:
    """e.g. BF-7K2P9X (31^6, about 900 million)."""
    return f"BF-{_code(6)}"


def ticket_number() -> str:
    """e.g. BFT-7K2P-9XQM (31^8, about 850 billion). Printed on the ticket and the PDF."""
    return f"BFT-{_code(4)}-{_code(4)}"
