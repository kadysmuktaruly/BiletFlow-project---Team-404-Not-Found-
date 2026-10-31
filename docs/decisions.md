# Decisions and assumptions

This file records decisions that the SRS (v0.3, [`docs/srs/`](srs/srs.md)) leaves open
(SRS §12), plus assumptions the code relies on. Model docstrings link here. When a decision
changes, update this file in the same PR.

## SRS §12 decisions

| Decision | Outcome | Where it shows up |
|---|---|---|
| Backend and database | Python (FastAPI, async SQLAlchemy) and PostgreSQL 16 | `apps/api` |
| Do attendees need an account? | **Yes.** Attendees must sign in to check out. There is no guest checkout. | `Order.user_id` and `SeatHold.user_id` are NOT NULL |
| Activation fee amount and refundability | `ACTIVATION_FEE_KZT` (default 5,000), **non-refundable** | `config.py`, `PaidSalesActivation.activation_fee_kzt` |
| Payment sandbox or simulation | **Internal simulation.** Every payment screen, email and record is labelled DEMO. | `Payment.provider = "simulated"`, `is_simulated` |
| Who pays processing charges | **The organizer.** They come out of the estimated payout, so attendees see only the ticket price. The rate is `PROCESSING_FEE_BPS` (default 300 = 3%), a demo placeholder. | `Order.processing_fee_kzt`, not part of `total_kzt` |
| Organizer verification | **A simulated checklist.** No real identity documents are collected (production KYC is excluded by SRS §8). | `PaidSalesActivation.identity_verified` |
| Promo discount types and limits | A percentage or a fixed KZT amount. One redemption limit per code. Reporting fields follow SRS §4.14: redemptions, orders, tickets sold, gross revenue, discount amount, net revenue. | `PromotionalCampaign`, `PromoCode`, `PromoRedemption` |
| Predefined seating layout | Deferred. Assigned seating is a bonus feature (semester plan, Report 6). Reports 3 and 4 are general admission only. | |

## Data model assumptions

- **`PaidSalesActivation` (the 26th model)** is not in the SRS §6 entity list. SRS §4.5 and §4.12
  need a per-event activation record, so it gets its own table.
- **`PromoCodeTicketType` (the 27th model)** stores a code's "applicable ticket types". No rows
  means the code applies to every ticket type on the event.

## Behaviour assumptions (Reports 2–4)

- Self-registration may choose only `attendee` or `organizer`. Platform admins are created by
  the seed script. Event admins come from `StaffAssignment`, not from `User.role`.
- Publishing an event requires a verified email (SRS UC1 precondition). Checkout does not.
- A `private` event is visible only to its organizer and assigned staff, because the schema
  has no invite-link token. An `unlisted` event opens by its slug but is not listed.
- **Admission token:** `BFT1.<ticket id>.<HMAC>`, signed with `TICKET_SIGNING_SECRET`. It
  identifies the ticket; the ticket's status is always read live at check-in.
- **Campaign token:** an opaque `BFC1.<random>` value. It carries no price or discount. The
  check-in endpoint accepts only `BFT1.` payloads, so it can never admit someone on a
  Campaign QR.
- A paid order reserves stock for `ORDER_RESERVATION_TTL_SECONDS` (default 600). When the order
  expires, fails, or is abandoned, the stock and any promo redemption are released.
- `PromoCode.redeemed_count` counts redemptions on confirmed orders **and** pending ones. It goes
  up when an order is created and back down if that order never confirms. That is what makes
  `ck_promo_codes_within_limit` hold under concurrent checkout.
- Event owners and `StaffRole.EVENT_ADMIN` assignees can undo a check-in.
  `StaffRole.CHECK_IN_STAFF` assignees can scan but not undo.
- Cancelling an event cancels its valid tickets and pending orders. Automatic refunds of paid
  orders are Report 5 work (SRS §4.9).
