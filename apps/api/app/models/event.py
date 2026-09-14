"""Event, Ticket Type, and Paid Sales Activation (SRS 4.2, 4.3, 4.5)."""

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

from app.enums import (
    ActivationStatus,
    EventStatus,
    EventVisibility,
    SeatingMode,
)
from app.models.base import Base, TimestampMixin, pg_enum, uuid_pk


class Event(Base, TimestampMixin):
    """SRS 4.2. Physical, venue-based events only for the MVP."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = uuid_pk()
    organizer_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizer_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("venues.id", ondelete="RESTRICT")
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(320), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    cover_image_url: Mapped[str | None] = mapped_column(String(500))

    status: Mapped[EventStatus] = mapped_column(
        pg_enum(EventStatus, "event_status"), nullable=False, default=EventStatus.DRAFT
    )
    visibility: Mapped[EventVisibility] = mapped_column(
        pg_enum(EventVisibility, "event_visibility"),
        nullable=False,
        default=EventVisibility.PUBLIC,
    )
    seating_mode: Mapped[SeatingMode] = mapped_column(
        pg_enum(SeatingMode, "seating_mode"),
        nullable=False,
        default=SeatingMode.GENERAL_ADMISSION,
    )

    starts_at: Mapped[datetime] = mapped_column(nullable=False)
    ends_at: Mapped[datetime] = mapped_column(nullable=False)
    # SRS 7: "Calendar exports shall preserve the event's configured time zone."
    # An IANA name, not a UTC offset: "Asia/Almaty", not "+05:00". An offset cannot
    # survive a DST transition or a government time-zone change, and Kazakhstan moved
    # the whole country to a single offset in 2024 — precisely the event that breaks
    # stored offsets. `starts_at` stays TIMESTAMPTZ; this is the display/export zone.
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Almaty")

    registration_opens_at: Mapped[datetime | None] = mapped_column()
    registration_closes_at: Mapped[datetime | None] = mapped_column()

    capacity: Mapped[int | None] = mapped_column(Integer)

    published_at: Mapped[datetime | None] = mapped_column()
    cancelled_at: Mapped[datetime | None] = mapped_column()
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    # SRS 4.9: organizers define a refund policy; the text is theirs, not the platform's.
    refund_policy: Mapped[str | None] = mapped_column(Text)

    # SRS 4.12: Platform Admins can suspend an event and stop further sales.
    is_suspended: Mapped[bool] = mapped_column(nullable=False, default=False)

    # SRS 4.16: duplicating a past event into a new draft, without its transactions.
    duplicated_from_event_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL")
    )

    ticket_types: Mapped[list[TicketType]] = relationship(back_populates="event")
    activation: Mapped[PaidSalesActivation | None] = relationship(
        back_populates="event", uselist=False
    )

    __table_args__ = (
        UniqueConstraint("slug", name="uq_events_slug"),
        CheckConstraint("ends_at >= starts_at", name="ck_events_end_after_start"),
        Index("ix_events_organizer_status", "organizer_profile_id", "status"),
        # Public listing (SRS 4.2) scans published, publicly visible, upcoming events.
        Index(
            "ix_events_public_listing",
            "starts_at",
            postgresql_where=text("status = 'published' AND visibility = 'public'"),
        ),
    )


class TicketType(Base, TimestampMixin):
    """SRS 4.3. Free and paid types, with their own sale window and per-order limit."""

    __tablename__ = "ticket_types"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Whole KZT. A free ticket type is price_kzt = 0, not NULL — "free" is a price, and
    # making it nullable would put a NULL into every sum in the analytics dashboard.
    price_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    quantity_total: Mapped[int] = mapped_column(Integer, nullable=False)
    # SRS 4.3: "The system shall prevent ticket sales when inventory has been exhausted."
    # TODO(week-5): maintained atomically alongside order confirmation, not recomputed.
    quantity_sold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    max_per_order: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    sales_start_at: Mapped[datetime | None] = mapped_column()
    sales_end_at: Mapped[datetime | None] = mapped_column()

    # SRS 4.3: "Hide ticket types without deleting them."
    is_hidden: Mapped[bool] = mapped_column(nullable=False, default=False)

    event: Mapped[Event] = relationship(back_populates="ticket_types")

    __table_args__ = (
        CheckConstraint("price_kzt >= 0", name="ck_ticket_types_price_non_negative"),
        CheckConstraint("quantity_total >= 0", name="ck_ticket_types_quantity_non_negative"),
        # The inventory guarantee, enforced by the database rather than by the handler
        # that happens to remember it. SRS 4.3.
        CheckConstraint(
            "quantity_sold >= 0 AND quantity_reserved >= 0 "
            "AND quantity_sold + quantity_reserved <= quantity_total",
            name="ck_ticket_types_inventory_within_total",
        ),
        CheckConstraint("max_per_order > 0", name="ck_ticket_types_max_per_order_positive"),
        Index("ix_ticket_types_event", "event_id"),
    )


class PaidSalesActivation(Base, TimestampMixin):
    """Per-event paid-sales activation (SRS 4.5).

    Not in the SRS 6 entity list, but SRS 4.5 requires the system to "record payment of
    the activation fee", SRS 4.12 requires Platform Admins to "inspect paid-sales
    activation records", and the checklist in 4.5 is per-event state that has nowhere
    else to live. Recorded as an assumption in docs/decisions.md.

    SRS 4.5: "Activation shall apply only to the selected event" — hence one row per
    event, not per organizer.
    """

    __tablename__ = "paid_sales_activations"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ActivationStatus] = mapped_column(
        pg_enum(ActivationStatus, "activation_status"),
        nullable=False,
        default=ActivationStatus.NOT_STARTED,
    )

    # The SRS 3.2 checklist, as five booleans the organizer-facing endpoint renders.
    has_paid_ticket_type: Mapped[bool] = mapped_column(nullable=False, default=False)
    identity_verified: Mapped[bool] = mapped_column(nullable=False, default=False)
    payout_account_connected: Mapped[bool] = mapped_column(nullable=False, default=False)
    activation_fee_paid: Mapped[bool] = mapped_column(nullable=False, default=False)
    terms_accepted: Mapped[bool] = mapped_column(nullable=False, default=False)

    activation_fee_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    activation_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL")
    )
    payout_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("payout_accounts.id", ondelete="SET NULL")
    )

    activated_at: Mapped[datetime | None] = mapped_column()
    # SRS 4.5: suspension by a Platform Admin where fraud is suspected.
    suspended_at: Mapped[datetime | None] = mapped_column()
    suspended_reason: Mapped[str | None] = mapped_column(Text)

    event: Mapped[Event] = relationship(back_populates="activation")

    __table_args__ = (
        UniqueConstraint("event_id", name="uq_activation_event"),
        CheckConstraint("activation_fee_kzt >= 0", name="ck_activation_fee_non_negative"),
    )
