"""Order, Order Item, Ticket, Attendee, Payment, Refund, Check-In Record (SRS 6)."""

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
    CheckInMethod,
    OrderStatus,
    PaymentPurpose,
    PaymentStatus,
    RefundStatus,
    TicketStatus,
)
from app.models.base import Base, TimestampMixin, pg_enum, uuid_pk


class Order(Base, TimestampMixin):
    """SRS 4.4, 4.6, 4.9.

    `user_id` is NOT NULL: attendee accounts are required for the MVP (docs/decisions.md).
    Every money column is server-computed — no endpoint accepts a price or discount from
    a client (SRS 7, SRS 4.14).
    """

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Human-facing reference, e.g. "BF-4K2P9X". Not the primary key — an attendee should
    # not have to read a UUID aloud to support staff.
    reference: Mapped[str] = mapped_column(String(32), nullable=False)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="RESTRICT"), nullable=False
    )

    status: Mapped[OrderStatus] = mapped_column(
        pg_enum(OrderStatus, "order_status"), nullable=False, default=OrderStatus.PENDING
    )

    # SRS 4.4: a free registration is an order with a zero-value total, not a separate
    # kind of object. One code path serves free and paid.
    subtotal_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    discount_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    processing_fee_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    refunded_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KZT")

    # SRS 4.14: the sale is attributed to the campaign, server-side.
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("promotional_campaigns.id", ondelete="SET NULL")
    )
    promo_code_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("promo_codes.id", ondelete="SET NULL")
    )

    confirmed_at: Mapped[datetime | None] = mapped_column()
    cancelled_at: Mapped[datetime | None] = mapped_column()
    # SRS 4.6: inventory is reserved temporarily during checkout.
    expires_at: Mapped[datetime | None] = mapped_column()

    items: Mapped[list[OrderItem]] = relationship(back_populates="order")
    tickets: Mapped[list[Ticket]] = relationship(back_populates="order")

    __table_args__ = (
        UniqueConstraint("reference", name="uq_orders_reference"),
        CheckConstraint(
            "subtotal_kzt >= 0 AND discount_kzt >= 0 AND processing_fee_kzt >= 0 "
            "AND total_kzt >= 0 AND refunded_kzt >= 0",
            name="ck_orders_money_non_negative",
        ),
        # A discount can zero an order but never make it negative. SRS 4.14 requires the
        # server to validate every discount; this is that rule as a constraint.
        CheckConstraint("discount_kzt <= subtotal_kzt", name="ck_orders_discount_within_subtotal"),
        CheckConstraint("refunded_kzt <= total_kzt", name="ck_orders_refund_within_total"),
        Index("ix_orders_user_created", "user_id", "created_at"),
        Index("ix_orders_event_status", "event_id", "status"),
        # SRS 4.15: "sales over time using order timestamps".
        Index(
            "ix_orders_event_confirmed_at",
            "event_id",
            "confirmed_at",
            postgresql_where=text("status = 'confirmed'"),
        ),
    )


class OrderItem(Base, TimestampMixin):
    """One line of an order: a ticket type, a quantity, and the price charged.

    `unit_price_kzt` is a snapshot taken at confirmation. If an organizer later edits the
    ticket type's price (SRS 4.16 logs exactly that), historical orders must not change
    underneath the attendee who already paid.
    """

    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    ticket_type_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ticket_types.id", ondelete="RESTRICT"), nullable=False
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_total_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # SRS 4.3.1: "The assigned section, row, and seat number shall be stored on the ticket
    # and order item." Denormalised text, deliberately: the label the attendee was sold is
    # a fact about the sale, and must survive the venue being relabelled later.
    seat_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("seats.id", ondelete="SET NULL")
    )
    seat_section: Mapped[str | None] = mapped_column(String(120))
    seat_row: Mapped[str | None] = mapped_column(String(20))
    seat_number: Mapped[str | None] = mapped_column(String(20))

    order: Mapped[Order] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        CheckConstraint(
            "unit_price_kzt >= 0 AND discount_kzt >= 0 AND line_total_kzt >= 0",
            name="ck_order_items_money_non_negative",
        ),
        Index("ix_order_items_order", "order_id"),
    )


class Attendee(Base, TimestampMixin):
    """The person admitted by a ticket (SRS 6).

    Distinct from the purchasing `User`: one account can buy four tickets for four named
    people. `user_id` is nullable because a guest of the purchaser need not have an
    account — the *purchaser* always does.
    """

    __tablename__ = "attendees"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (Index("ix_attendees_order", "order_id"),)


class Ticket(Base, TimestampMixin):
    """An issued admission (SRS 4.7).

    `uq_ticket_active_seat` in `__table_args__` is the database-level guarantee behind
    SRS 4.3.1's "prevent two orders from purchasing the same seat, including when multiple
    attendees check out concurrently". Nothing above the database needs to be correct for
    it to hold.
    """

    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = uuid_pk()
    # SRS 4.7: "A unique ticket identifier", shared by the digital and printed copy so
    # they "shall not create separate admissions".
    ticket_number: Mapped[str] = mapped_column(String(40), nullable=False)

    order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False
    )
    # Denormalised from the order so the seat uniqueness index needs no join.
    event_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="RESTRICT"), nullable=False
    )
    ticket_type_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ticket_types.id", ondelete="RESTRICT"), nullable=False
    )
    attendee_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("attendees.id", ondelete="RESTRICT"), nullable=False
    )

    status: Mapped[TicketStatus] = mapped_column(
        pg_enum(TicketStatus, "ticket_status"), nullable=False, default=TicketStatus.VALID
    )

    # SRS 4.14 / 7: the admission token. Opaque and server-side; it encodes nothing.
    # Its wire format carries the `BFT1.` prefix that makes a Campaign QR structurally
    # unable to reach this table — see app/schemas/scan.py.
    admission_token: Mapped[str] = mapped_column(String(64), nullable=False)

    # NULL for general admission. SRS 4.3.1 requires the seat be stored on the ticket.
    seat_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("seats.id", ondelete="SET NULL")
    )
    seat_section: Mapped[str | None] = mapped_column(String(120))
    seat_row: Mapped[str | None] = mapped_column(String(20))
    seat_number: Mapped[str | None] = mapped_column(String(20))

    price_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    issued_at: Mapped[datetime | None] = mapped_column()
    checked_in_at: Mapped[datetime | None] = mapped_column()
    cancelled_at: Mapped[datetime | None] = mapped_column()
    refunded_at: Mapped[datetime | None] = mapped_column()

    order: Mapped[Order] = relationship(back_populates="tickets")

    __table_args__ = (
        UniqueConstraint("ticket_number", name="uq_tickets_number"),
        UniqueConstraint("admission_token", name="uq_tickets_admission_token"),
        CheckConstraint("price_kzt >= 0", name="ck_tickets_price_non_negative"),
        # ------------------------------------------------------------------
        # SRS 4.3.1 / SRS 7: two orders can never hold the same seat.
        #
        # Partial, so that cancelling or refunding a ticket drops it out of the index
        # and returns the seat to sale. `seat_id IS NOT NULL` keeps every general-
        # admission ticket out entirely — otherwise the whole GA inventory would
        # collide on a single NULL seat.
        # ------------------------------------------------------------------
        Index(
            "uq_ticket_active_seat",
            "event_id",
            "seat_id",
            unique=True,
            postgresql_where=text(
                "seat_id IS NOT NULL AND status NOT IN ('cancelled', 'refunded')"
            ),
        ),
        Index("ix_tickets_event_status", "event_id", "status"),
        Index("ix_tickets_order", "order_id"),
    )


class Payment(Base, TimestampMixin):
    """A charge (SRS 4.6).

    `is_simulated` is NOT NULL and defaults to True. SRS 4.6: "Demonstration payment
    records shall never be presented as real financial transactions." The flag is
    required in every response schema that carries a payment, so it has no opportunity to
    be dropped between here and the client.

    SRS 7 forbids the platform storing payment-card data. There is therefore no PAN, no
    expiry, and no CVV column — only a provider reference and a masked brand/last-4 for
    display.
    """

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = uuid_pk()
    purpose: Mapped[PaymentPurpose] = mapped_column(
        pg_enum(PaymentPurpose, "payment_purpose"), nullable=False
    )
    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"), nullable=False, default=PaymentStatus.PENDING
    )

    order_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL")
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    amount_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KZT")

    provider: Mapped[str] = mapped_column(String(60), nullable=False, default="simulated")
    provider_reference: Mapped[str | None] = mapped_column(String(200))
    # Display only. Never the full number — see the class docstring.
    card_brand: Mapped[str | None] = mapped_column(String(40))
    card_last4: Mapped[str | None] = mapped_column(String(4))

    is_simulated: Mapped[bool] = mapped_column(nullable=False, default=True)

    # SRS 4.6: a failed transaction must not yield a valid ticket. Retries key on this.
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    succeeded_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
        CheckConstraint("amount_kzt >= 0", name="ck_payments_amount_non_negative"),
        Index("ix_payments_order", "order_id"),
        Index("ix_payments_event", "event_id"),
    )


class Refund(Base, TimestampMixin):
    """SRS 4.9. Refunded tickets become invalid and drop out of `uq_ticket_active_seat`."""

    __tablename__ = "refunds"

    id: Mapped[uuid.UUID] = uuid_pk()
    payment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[RefundStatus] = mapped_column(
        pg_enum(RefundStatus, "refund_status"), nullable=False, default=RefundStatus.PENDING
    )
    amount_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KZT")
    reason: Mapped[str | None] = mapped_column(Text)

    initiated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    is_simulated: Mapped[bool] = mapped_column(nullable=False, default=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(200))
    succeeded_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_refunds_idempotency_key"),
        CheckConstraint("amount_kzt >= 0", name="ck_refunds_amount_non_negative"),
        Index("ix_refunds_order", "order_id"),
    )


class CheckInRecord(Base, TimestampMixin):
    """SRS 4.8.

    An append-style log rather than a boolean on the ticket, because SRS 4.8 allows an
    accidental check-in to be undone "where authorized" and SRS 4.16 requires both the
    check-in and the reversal to appear on the event timeline. A `reversed_at` row still
    tells that story; a flipped boolean does not.

    `uq_checkin_active_ticket` is what enforces "prevent the same ticket from being used
    twice" — one un-reversed check-in per ticket, in the database.
    """

    __tablename__ = "check_in_records"

    id: Mapped[uuid.UUID] = uuid_pk()
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    checked_in_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    method: Mapped[CheckInMethod] = mapped_column(
        pg_enum(CheckInMethod, "check_in_method"), nullable=False, default=CheckInMethod.QR_SCAN
    )
    checked_in_at: Mapped[datetime] = mapped_column(nullable=False)

    reversed_at: Mapped[datetime | None] = mapped_column()
    reversed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reversal_reason: Mapped[str | None] = mapped_column(Text)
    device_label: Mapped[str | None] = mapped_column(String(120))

    __table_args__ = (
        Index(
            "uq_checkin_active_ticket",
            "ticket_id",
            unique=True,
            postgresql_where=text("reversed_at IS NULL"),
        ),
        Index("ix_check_in_records_event", "event_id", "checked_in_at"),
    )
