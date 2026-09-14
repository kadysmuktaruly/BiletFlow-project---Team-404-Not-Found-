"""User, Organizer Profile, Payout Account, Staff Assignment, Notification (SRS 6)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import (
    NotificationChannel,
    NotificationStatus,
    NotificationType,
    PayoutAccountStatus,
    StaffRole,
    UserRole,
)
from app.models.base import Base, TimestampMixin, pg_enum, uuid_pk


class User(Base, TimestampMixin):
    """SRS 4.1. Email registration, email verification, role-based permissions.

    `role` is the user's *platform* role. Being an Event Admin for one event does not make
    someone an Event Admin globally — that authorisation lives in `StaffAssignment`, and
    `require_event_admin` in `app/deps.py` checks the assignment, not this column.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    # SRS 7: "Passwords shall be stored using secure password hashing."
    # TODO(week-3): populated by the Argon2/bcrypt hasher; never store a plaintext password.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"), nullable=False, default=UserRole.ATTENDEE
    )
    # SRS 7: Kazakh and Russian first, English as an additional locale.
    locale: Mapped[str] = mapped_column(String(8), nullable=False, default="kk")

    is_email_verified: Mapped[bool] = mapped_column(nullable=False, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column()
    # SRS 4.12: Platform Admins can suspend users.
    is_suspended: Mapped[bool] = mapped_column(nullable=False, default=False)
    suspended_at: Mapped[datetime | None] = mapped_column()

    organizer_profile: Mapped[OrganizerProfile | None] = relationship(
        back_populates="user", uselist=False
    )

    __table_args__ = (
        # Case-insensitive uniqueness. Two accounts differing only in capitalisation are
        # the same person to everyone except a naive UNIQUE constraint.
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
    )


class OrganizerProfile(Base, TimestampMixin):
    """SRS 4.1: "Organizers shall have a profile containing contact and payout information"."""

    __tablename__ = "organizer_profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(String(500))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    is_suspended: Mapped[bool] = mapped_column(nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="organizer_profile")
    payout_accounts: Mapped[list[PayoutAccount]] = relationship(back_populates="organizer_profile")

    __table_args__ = (UniqueConstraint("user_id", name="uq_organizer_profile_user"),)


class PayoutAccount(Base, TimestampMixin):
    """SRS 3.2 step 4: a valid payout account is a precondition of paid-sales activation.

    Stores a **masked tail only**. SRS 7 forbids the platform from holding payment-card
    data directly, and real payouts are excluded from the MVP entirely (SRS 8) — there is
    no business reason for a full account number to exist in this table, so the column for
    it does not exist either.
    """

    __tablename__ = "payout_accounts"

    id: Mapped[uuid.UUID] = uuid_pk()
    organizer_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizer_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_holder_name: Mapped[str] = mapped_column(String(200), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[PayoutAccountStatus] = mapped_column(
        pg_enum(PayoutAccountStatus, "payout_account_status"),
        nullable=False,
        default=PayoutAccountStatus.UNVERIFIED,
    )
    verified_at: Mapped[datetime | None] = mapped_column()
    # SRS 4.6: demonstration records must never read as real financial instruments.
    is_simulated: Mapped[bool] = mapped_column(nullable=False, default=True)

    organizer_profile: Mapped[OrganizerProfile] = relationship(back_populates="payout_accounts")


class StaffAssignment(Base, TimestampMixin):
    """SRS 4.8: an Event Admin signs in and views **only assigned events**.

    This table is that authorisation. `require_event_admin` resolves against it rather
    than against `User.role`, which is why the dependency takes an `event_id`.
    """

    __tablename__ = "staff_assignments"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[StaffRole] = mapped_column(
        pg_enum(StaffRole, "staff_role"), nullable=False, default=StaffRole.EVENT_ADMIN
    )
    assigned_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        # One live assignment per person per event. Revoked rows are retained for audit
        # (SRS 4.16) and fall out of the index, so a person can be re-assigned later.
        Index(
            "uq_staff_assignment_active",
            "event_id",
            "user_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class Notification(Base, TimestampMixin):
    """SRS 4.10 and 4.13. Delivery itself is Week 3+ work; this is the record of it."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[NotificationType] = mapped_column(
        pg_enum(NotificationType, "notification_type"), nullable=False
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        pg_enum(NotificationChannel, "notification_channel"), nullable=False
    )
    status: Mapped[NotificationStatus] = mapped_column(
        pg_enum(NotificationStatus, "notification_status"),
        nullable=False,
        default=NotificationStatus.PENDING,
    )
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Contextual links, all optional — a payout notification has no ticket.
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL")
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL")
    )
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tickets.id", ondelete="SET NULL")
    )

    sent_at: Mapped[datetime | None] = mapped_column()
    read_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)
