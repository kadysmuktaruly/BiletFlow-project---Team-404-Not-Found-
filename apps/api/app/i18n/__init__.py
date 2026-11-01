"""Locales the platform speaks (SRS 7: Kazakh and Russian first, English as well)."""

from typing import Literal, get_args

Locale = Literal["kk", "ru", "en"]
SUPPORTED_LOCALES: tuple[str, ...] = get_args(Locale)
DEFAULT_LOCALE: Locale = "kk"


def normalize_locale(value: str | None) -> Locale:
    if value in SUPPORTED_LOCALES:
        return value  # type: ignore[return-value]
    return DEFAULT_LOCALE
