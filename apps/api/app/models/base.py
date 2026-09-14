"""Declarative base and the column conventions every BiletFlow table follows."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """All BiletFlow tables inherit these mapping conventions.

    `type_annotation_map` is the important part: it makes a bare `Mapped[datetime]`
    resolve to **TIMESTAMPTZ**, not the naive TIMESTAMP SQLAlchemy would otherwise infer.
    SRS 7 requires timezone-aware storage, and relying on each model to remember
    `DateTime(timezone=True)` on every nullable column is exactly the kind of thing that
    holds for a week and then quietly stops holding.
    """

    type_annotation_map = {  # noqa: RUF012
        datetime: DateTime(timezone=True),
    }


def pg_enum[E: StrEnum](enum_cls: type[E], name: str) -> SAEnum:
    """A native Postgres enum type that stores member **values**, not member names.

    SQLAlchemy's default is to persist `UserRole.ORGANIZER` as the string ``ORGANIZER``.
    Every partial index predicate in this schema is written against the lowercase value
    (``status = 'active'``, ``status NOT IN ('cancelled','refunded')``), so without
    `values_callable` those predicates would silently match nothing and the uniqueness
    guarantees would not hold. Always build status columns through this helper.
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda e: [member.value for member in e],
    )


def uuid_pk() -> Mapped[uuid.UUID]:
    """UUID primary key, defaulted on **both** sides.

    `default=uuid.uuid4` is Python-side, so an async insert through the ORM knows the id
    without a RETURNING round trip and tests can wire up object graphs before flushing.

    `server_default=gen_random_uuid()` covers the other half: seed scripts, fixtures, and
    anything written in raw SQL. Without it, every hand-written INSERT has to supply a
    UUID literal, and the failure mode is a NOT NULL violation that reads like a schema
    bug rather than a missing column. Built into Postgres 13+, so no pgcrypto extension.
    """
    return mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


def fk_uuid() -> Mapped[uuid.UUID]:
    return mapped_column(PGUUID(as_uuid=True))


def money_kzt() -> Mapped[int]:
    """Whole Kazakhstani tenge, as an integer. Never Float, never Numeric.

    BigInteger rather than Integer: int32 tops out near 2.1 billion, and an event's
    gross-sales or payout aggregate can plausibly reach that in KZT.
    """
    return mapped_column(BigInteger)


class TimestampMixin:
    """TIMESTAMPTZ created/updated, per SRS 7.

    Every timestamp in this schema is timezone-aware. An event's *display* time zone is a
    separate IANA string on `Event` — see the note there.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
