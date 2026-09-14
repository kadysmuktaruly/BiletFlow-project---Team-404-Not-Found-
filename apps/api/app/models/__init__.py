"""All 27 BiletFlow tables.

SRS Section 6 lists 25 core entities. `PaidSalesActivation` is the 26th, added because
SRS 4.5 and 4.12 require activation records that Section 6 omits — see docs/decisions.md.
`PromoCodeTicketType` is the 27th, a plain association table for SRS 4.14's
"applicable ticket types".

Importing this package registers every model on `Base.metadata`, which is what Alembic
autogenerate walks. A model that is not reachable from here does not exist as far as
migrations are concerned.
"""

from app.models.audit import AuditLogEntry
from app.models.base import Base
from app.models.campaign import (
    PromoCode,
    PromoCodeTicketType,
    PromoRedemption,
    PromotionalCampaign,
)
from app.models.event import Event, PaidSalesActivation, TicketType
from app.models.order import (
    Attendee,
    CheckInRecord,
    Order,
    OrderItem,
    Payment,
    Refund,
    Ticket,
)
from app.models.seating import Row, Seat, SeatHold, Venue, VenueSection
from app.models.support import SupportCase, SupportMessage
from app.models.user import (
    Notification,
    OrganizerProfile,
    PayoutAccount,
    StaffAssignment,
    User,
)

__all__ = [
    "Attendee",
    "AuditLogEntry",
    "Base",
    "CheckInRecord",
    "Event",
    "Notification",
    "Order",
    "OrderItem",
    "OrganizerProfile",
    "PaidSalesActivation",
    "Payment",
    "PayoutAccount",
    "PromoCode",
    "PromoCodeTicketType",
    "PromoRedemption",
    "PromotionalCampaign",
    "Refund",
    "Row",
    "Seat",
    "SeatHold",
    "StaffAssignment",
    "SupportCase",
    "SupportMessage",
    "Ticket",
    "TicketType",
    "User",
    "Venue",
    "VenueSection",
]
