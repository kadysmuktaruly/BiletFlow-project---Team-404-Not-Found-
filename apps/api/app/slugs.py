"""URL slugs for events: readable Latin text plus a random suffix.

Titles are often Kazakh or Russian, so Cyrillic is transliterated first. The suffix keeps
slugs unique without exposing a sequence, and lets two events share a title.
"""

import re
import secrets
import unicodedata

_CYRILLIC = {
    "а": "a", "ә": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d", "е": "e",
    "ё": "yo", "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "қ": "q", "л": "l",
    "м": "m", "н": "n", "ң": "n", "о": "o", "ө": "o", "п": "p", "р": "r", "с": "s",
    "т": "t", "у": "u", "ұ": "u", "ү": "u", "ф": "f", "х": "kh", "һ": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "і": "i", "ь": "", "э": "e",
    "ю": "yu", "я": "ya",
}  # fmt: skip

_MAX_BASE = 60
_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  # no 0/o or 1/l lookalikes


def slugify(text: str) -> str:
    lowered = "".join(_CYRILLIC.get(ch, ch) for ch in text.lower())
    ascii_text = unicodedata.normalize("NFKD", lowered).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return base[:_MAX_BASE].rstrip("-") or "event"


def event_slug(title: str) -> str:
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(6))
    return f"{slugify(title)}-{suffix}"
