"""Promotional Campaign, Promo Code, Promo Redemption (SRS 4.14).

Two SRS rules shape this module and are worth stating up front:

1. SRS 4.14 / 7: "Campaign QR links shall not contain trusted price or discount values."
   `PromotionalCampaign.qr_token` is an opaque lookup key. The discount lives on the
   campaign row, server-side, and is read only after the token resolves.
2. SRS 7: "Promo-code validation and redemption limits shall be enforced atomically on
   the server." See `ck_promo_codes_within_limit` below — that constraint, not the
   handler, is what makes the limit hold under concurrent checkout.
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

from app.enums import CampaignStatus, DiscountType
from app.models.base import Base, TimestampMixin, pg_enum, uuid_pk


class PromotionalCampaign(Base, TimestampMixin):
    """SRS 4.14: an organizer-created campaign for one event."""

    __tablename__ = "promotional_campaigns"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    status: Mapped[CampaignStatus] = mapped_column(
        pg_enum(CampaignStatus, "campaign_status"),
        nullable=False,
        default=CampaignStatus.DRAFT,
    )

    discount_type: Mapped[DiscountType] = mapped_column(
        pg_enum(DiscountType, "discount_type"), nullable=False
    )
    # Exactly one of these is set, enforced by ck_campaign_discount_shape below.
    discount_percent: Mapped[int | None] = mapped_column(Integer)
    discount_kzt: Mapped[int | None] = mapped_column(BigInteger)

    starts_at: Mapped[datetime | None] = mapped_column()
    ends_at: Mapped[datetime | None] = mapped_column()

    # ------------------------------------------------------------------
    # SRS 4.14: "The Campaign QR Code shall encode a trackable HTTPS event link
    # containing an opaque campaign or promo token rather than a discount amount trusted
    # by the client."
    #
    # This column is that token, and it is all the link carries. The discount above is
    # never serialised into a URL. Its wire format uses the `BFC1.` prefix, which is
    # disjoint from the `BFT1.` admission prefix — see app/schemas/scan.py for why that
    # makes the check-in endpoint structurally unable to accept one.
    # ------------------------------------------------------------------
    qr_token: Mapped[str] = mapped_column(String(64), nullable=False)

    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    disabled_at: Mapped[datetime | None] = mapped_column()

    promo_codes: Mapped[list[PromoCode]] = relationship(back_populates="campaign")

    __table_args__ = (
        UniqueConstraint("qr_token", name="uq_campaign_qr_token"),
        CheckConstraint(
            "(discount_type = 'percentage' AND discount_percent IS NOT NULL "
            " AND discount_percent BETWEEN 1 AND 100 AND discount_kzt IS NULL) "
            "OR (discount_type = 'fixed_kzt' AND discount_kzt IS NOT NULL "
            " AND discount_kzt >= 0 AND discount_percent IS NULL)",
            name="ck_campaign_discount_shape",
        ),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at",
            name="ck_campaign_window",
        ),
        Index("ix_campaigns_event", "event_id"),
    )


class PromoCode(Base, TimestampMixin):
    """SRS 4.14: the code an attendee types, or that a Campaign QR applies automatically.

    `redeemed_count` plus `ck_promo_codes_within_limit` is the atomic redemption limit
    SRS 7 requires. A plain

        UPDATE promo_codes SET redeemed_count = redeemed_count + 1 WHERE id = :id

    is rejected by Postgres if it would push the count past `max_redemptions`, under any
    interleaving of concurrent checkouts. No read-then-write, no advisory lock, no
    application-level race to lose.
    """

    __tablename__ = "promo_codes"

    id: Mapped[uuid.UUID] = uuid_pk()
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("promotional_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)

    max_redemptions: Mapped[int | None] = mapped_column(Integer)
    redeemed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # SRS 4.14: "applicable ticket types". See PromoCodeTicketType below — an empty
    # restriction set means the code applies to every ticket type on the event.

    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    campaign: Mapped[PromotionalCampaign] = relationship(back_populates="promo_codes")
    ticket_type_restrictions: Mapped[list[PromoCodeTicketType]] = relationship(
        back_populates="promo_code"
    )

    __table_args__ = (
        # Case-insensitive: an attendee typing "summer10" and "SUMMER10" means one code.
        Index("uq_promo_codes_code_lower", text("lower(code)"), unique=True),
        CheckConstraint(
            "redeemed_count >= 0 "
            "AND (max_redemptions IS NULL OR redeemed_count <= max_redemptions)",
            name="ck_promo_codes_within_limit",
        ),
        CheckConstraint(
            "max_redemptions IS NULL OR max_redemptions > 0",
            name="ck_promo_codes_max_redemptions_positive",
        ),
        Index("ix_promo_codes_campaign", "campaign_id"),
    )


class PromoCodeTicketType(Base, TimestampMixin):
    """Which ticket types a promo code applies to (SRS 4.14).

    An association table rather than an array or a comma-joined string column on
    `PromoCode`. The SRS calls the field "applicable ticket types", and the natural
    shortcut — stashing a list of UUIDs in one column — buys nothing and gives up the
    foreign key: delete a ticket type and the code keeps pointing at an id that no longer
    resolves, which surfaces in Week 5 as a discount that silently applies to nothing.

    **No rows means no restriction**, i.e. the code applies to every ticket type on the
    event. That is the common case, so the common case costs no rows at all.
    """

    __tablename__ = "promo_code_ticket_types"

    id: Mapped[uuid.UUID] = uuid_pk()
    promo_code_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("promo_codes.id", ondelete="CASCADE"), nullable=False
    )
    ticket_type_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ticket_types.id", ondelete="CASCADE"), nullable=False
    )

    promo_code: Mapped[PromoCode] = relationship(back_populates="ticket_type_restrictions")

    __table_args__ = (
        UniqueConstraint("promo_code_id", "ticket_type_id", name="uq_promo_code_ticket_type"),
    )


class PromoRedemption(Base, TimestampMixin):
    """One redemption of one code against one order (SRS 4.14).

    The unique constraint makes a redemption idempotent per order: a retried checkout
    confirmation cannot count twice against the campaign limit.

    Money columns are a record of what the **server** calculated, never what a client
    proposed (SRS 4.14: "The server shall calculate and validate all discounts").
    """

    __tablename__ = "promo_redemptions"

    id: Mapped[uuid.UUID] = uuid_pk()
    promo_code_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("promo_codes.id", ondelete="RESTRICT"), nullable=False
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("promotional_campaigns.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    discount_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_total_kzt: Mapped[int] = mapped_column(BigInteger, nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("promo_code_id", "order_id", name="uq_promo_redemption_code_order"),
        CheckConstraint(
            "discount_kzt >= 0 AND order_total_kzt >= 0",
            name="ck_promo_redemptions_money_non_negative",
        ),
        Index("ix_promo_redemptions_campaign", "campaign_id"),
    )
