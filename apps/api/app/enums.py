"""Every enumeration in BiletFlow, in one place.

Each of these is materialised as a **native Postgres enum type**. Note the
`values_callable` in `app.models.base.pg_enum`: without it SQLAlchemy persists the
Python member *name* (``ORGANIZER``), not its value (``organizer``). Every partial
index predicate and raw-SQL comparison in the schema is written against the
lowercase value, so that setting is load-bearing, not cosmetic.

`AuditLogEntry.action_type` and `.entity_type` are deliberately **not** enums — see
`app/models/audit.py` for why.
"""

from enum import StrEnum


class UserRole(StrEnum):
    """SRS 2.3. `EVENT_ADMIN` is organizer-delegated and distinct from `PLATFORM_ADMIN`."""

    ATTENDEE = "attendee"
    ORGANIZER = "organizer"
    EVENT_ADMIN = "event_admin"
    PLATFORM_ADMIN = "platform_admin"


class EventStatus(StrEnum):
    """Stored lifecycle, driven by the SRS 4.2 verbs (publish / unpublish / cancel).

    SRS 4.16's dashboard classification (Upcoming / Active / Completed / Cancelled) is
    *derived* from this plus the event's start and end times — it is not stored, because
    'Upcoming' becomes 'Active' with the passage of time and no row is written.
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class EventVisibility(StrEnum):
    """SRS 4.2: public, unlisted, or private."""

    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


class SeatingMode(StrEnum):
    """SRS 4.3.1: general admission or assigned seating."""

    GENERAL_ADMISSION = "general_admission"
    ASSIGNED_SEATING = "assigned_seating"


class TicketStatus(StrEnum):
    """SRS 4.7 names exactly these four.

    `CANCELLED` and `REFUNDED` are the two that drop a ticket out of the
    `uq_ticket_active_seat` partial index, freeing the seat for resale.
    """

    VALID = "valid"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class OrderStatus(StrEnum):
    """SRS 4.6: failed or abandoned transactions must never yield a valid ticket."""

    PENDING = "pending"
    AWAITING_PAYMENT = "awaiting_payment"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    FAILED = "failed"
    EXPIRED = "expired"


class SeatStatus(StrEnum):
    """The *stored* seat lifecycle.

    SRS 4.3.1 lists six seat appearances: available, selected, temporarily held, sold,
    unavailable, and accessible. Only four are persisted state. 'Selected' is transient
    client-side UI, and 'accessible' is a fixed attribute of the seat
    (`Seat.is_accessible`), not a status it moves through.
    """

    AVAILABLE = "available"
    HELD = "held"
    SOLD = "sold"
    UNAVAILABLE = "unavailable"


class SeatHoldStatus(StrEnum):
    """See `app/models/seating.py` — `ACTIVE` is the partial-unique-index predicate."""

    ACTIVE = "active"
    RELEASED = "released"
    CONVERTED = "converted"
    EXPIRED = "expired"


class SupportCaseStatus(StrEnum):
    """SRS 4.13 names exactly these four."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_CUSTOMER = "waiting_for_customer"
    RESOLVED = "resolved"


class SupportCategory(StrEnum):
    """SRS 4.13's issue categories, verbatim."""

    TICKET_DELIVERY = "ticket_delivery"
    PAYMENT = "payment"
    REFUND = "refund"
    SEATING = "seating"
    EVENT_INFORMATION = "event_information"
    CHECK_IN = "check_in"
    ACCOUNT = "account"
    TECHNICAL = "technical"


class PaymentPurpose(StrEnum):
    """SRS 3.2: the two things money is ever collected for."""

    ACTIVATION_FEE = "activation_fee"
    TICKET_ORDER = "ticket_order"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class RefundStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PayoutAccountStatus(StrEnum):
    """SRS 3.2 step 4. Production KYC/KYB is explicitly excluded from the MVP (SRS 8)."""

    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ActivationStatus(StrEnum):
    """SRS 4.5. `SUSPENDED` exists because 4.5 lets Platform Admins stop paid sales."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class CampaignStatus(StrEnum):
    """SRS 4.14: expired, disabled, and exhausted codes are each rejected distinctly."""

    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"
    EXHAUSTED = "exhausted"


class DiscountType(StrEnum):
    """SRS 4.14: 'a percentage or fixed-KZT discount'."""

    PERCENTAGE = "percentage"
    FIXED_KZT = "fixed_kzt"


class CheckInMethod(StrEnum):
    """SRS 4.8 allows both a camera scan and a manual attendee search."""

    QR_SCAN = "qr_scan"
    MANUAL_SEARCH = "manual_search"


class StaffRole(StrEnum):
    """SRS 4.8 / 2.3: an organizer authorises a user against one event."""

    EVENT_ADMIN = "event_admin"
    CHECK_IN_STAFF = "check_in_staff"


class NotificationChannel(StrEnum):
    """SRS 4.13: 'in-app or email'. Real-time delivery is out of MVP scope."""

    EMAIL = "email"
    IN_APP = "in_app"


class NotificationType(StrEnum):
    """SRS 4.10's list, verbatim, plus 4.13's three support notifications."""

    ACCOUNT_VERIFICATION = "account_verification"
    REGISTRATION_CONFIRMATION = "registration_confirmation"
    PAYMENT_FAILURE = "payment_failure"
    TICKET_DELIVERY = "ticket_delivery"
    EVENT_UPDATE = "event_update"
    EVENT_CANCELLATION = "event_cancellation"
    REFUND_COMPLETED = "refund_completed"
    PAYOUT_STATUS = "payout_status"
    SUPPORT_NEW_MESSAGE = "support_new_message"
    SUPPORT_CASE_ASSIGNED = "support_case_assigned"
    SUPPORT_STATUS_CHANGE = "support_status_change"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"
