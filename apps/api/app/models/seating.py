"""Venue, Venue Section, Row, Seat, Seat Hold (SRS 4.3.1).

The MVP ships **one predefined venue layout** (SRS 4.3.1, 8). There is no visual layout
editor — that is explicitly excluded in SRS 8 — so these tables are populated by a seed,
not by an organizer-facing CRUD surface.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import SeatHoldStatus, SeatStatus
from app.models.base import Base, TimestampMixin, pg_enum, uuid_pk


class Venue(Base, TimestampMixin):
    """A physical venue. SRS 4.2: physical, venue-based events only."""

    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    address_line1: Mapped[str] = mapped_column(String(300), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    region: Mapped[str | None] = mapped_column(String(120))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="KZ")
    postal_code: Mapped[str | None] = mapped_column(String(20))
    latitude: Mapped[str | None] = mapped_column(String(32))
    longitude: Mapped[str | None] = mapped_column(String(32))
    # SRS 4.3.1: the predefined layout organizers select rather than draw.
    has_seat_map: Mapped[bool] = mapped_column(nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    sections: Mapped[list[VenueSection]] = relationship(back_populates="venue")


class VenueSection(Base, TimestampMixin):
    """SRS 4.3.1: sections, each with a price category."""

    __tablename__ = "venue_sections"

    id: Mapped[uuid.UUID] = uuid_pk()
    venue_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # A label, not a price. The money lives on TicketType; a section that carried its own
    # price would give checkout two disagreeing sources for the same number.
    price_category: Mapped[str | None] = mapped_column(String(60))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    venue: Mapped[Venue] = relationship(back_populates="sections")
    rows: Mapped[list[Row]] = relationship(back_populates="section")

    __table_args__ = (UniqueConstraint("venue_id", "name", name="uq_venue_section_name"),)


class Row(Base, TimestampMixin):
    """SRS 6 calls this entity "Row".

    The table is `seat_rows`, not `rows`: ROWS is a reserved keyword in Postgres (window
    frame clauses), and a table named `rows` forces every query that touches it to quote
    the identifier forever. The Python class keeps the SRS name.
    """

    __tablename__ = "seat_rows"

    id: Mapped[uuid.UUID] = uuid_pk()
    section_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("venue_sections.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    section: Mapped[VenueSection] = relationship(back_populates="rows")
    seats: Mapped[list[Seat]] = relationship(back_populates="row")

    __table_args__ = (UniqueConstraint("section_id", "label", name="uq_seat_row_label"),)


class Seat(Base, TimestampMixin):
    """SRS 4.3.1.

    `is_accessible` is an attribute, not a status. SRS 4.3.1 lists "accessible" alongside
    available/held/sold in the seat-map legend, but an accessible seat is still available
    or sold — conflating the two would make an accessible seat unsellable.
    """

    __tablename__ = "seats"

    id: Mapped[uuid.UUID] = uuid_pk()
    row_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("seat_rows.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[str] = mapped_column(String(20), nullable=False)
    is_accessible: Mapped[bool] = mapped_column(nullable=False, default=False)
    status: Mapped[SeatStatus] = mapped_column(
        pg_enum(SeatStatus, "seat_status"), nullable=False, default=SeatStatus.AVAILABLE
    )
    # SVG/Canvas coordinates for the seat map (SRS 9: "React with SVG or Canvas").
    position_x: Mapped[int | None] = mapped_column(Integer)
    position_y: Mapped[int | None] = mapped_column(Integer)

    row: Mapped[Row] = relationship(back_populates="seats")

    __table_args__ = (
        UniqueConstraint("row_id", "number", name="uq_seat_number_in_row"),
        Index("ix_seats_row", "row_id"),
    )


class SeatHold(Base, TimestampMixin):
    """A temporary hold placed while checkout is in progress (SRS 4.3.1, SRS 7).

    Two indexes below carry the concurrency guarantee, and the exact predicate matters:

    `uq_seat_hold_active` is partial on ``status = 'active'`` and **not** on
    ``expires_at > now()``. `now()` is not IMMUTABLE and Postgres will not accept it in an
    index predicate. The consequence is a rule the Week 5-6 reservation code must honour:

        The expiry sweep is cleanup, not correctness.

    A hold that has passed `expires_at` but has not yet been swept is still `ACTIVE` in
    this index. So every reservation query must filter
    ``status = 'active' AND expires_at > now()`` itself. If it leans on the sweep having
    run, an abandoned checkout blocks a seat until the next sweep tick — the exact
    failure SRS 4.3.1 is written to prevent.
    """

    __tablename__ = "seat_holds"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    seat_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("seats.id", ondelete="CASCADE"), nullable=False
    )
    # The holder. Attendee accounts are required (see docs/decisions.md), so this is never
    # an anonymous session token.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL")
    )
    ticket_type_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ticket_types.id", ondelete="SET NULL")
    )

    status: Mapped[SeatHoldStatus] = mapped_column(
        pg_enum(SeatHoldStatus, "seat_hold_status"),
        nullable=False,
        default=SeatHoldStatus.ACTIVE,
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    released_at: Mapped[datetime | None] = mapped_column()

    # Quoted price at hold time, for display only. Checkout recomputes from TicketType —
    # SRS 7 requires the server to own every amount.
    quoted_price_kzt: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        # At most one live hold per seat. This is the database-level half of
        # "prevent two orders from purchasing the same seat"; the other half is
        # `uq_ticket_active_seat` on tickets.
        Index(
            "uq_seat_hold_active",
            "seat_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        # SRS 4.3.1: "A seat hold shall expire and release the seat." This index is what
        # lets the sweep find expiring holds without scanning the table.
        Index(
            "ix_seat_holds_expiry",
            "expires_at",
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_seat_holds_event", "event_id"),
        CheckConstraint(
            "quoted_price_kzt IS NULL OR quoted_price_kzt >= 0",
            name="ck_seat_holds_price_non_negative",
        ),
    )
