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

## Why FastAPI and PostgreSQL (SRS §9)

SRS §9 asks for the backend and database choice "with a short rationale covering team
familiarity, development speed, data-model requirements, and deployment complexity".

- **Team familiarity.** *To be completed by the team: which members knew Python, FastAPI
  and SQL beforehand, compared with Node/Express, Go or Spring Boot.* The web and scanner
  apps are TypeScript either way (SRS §9), so the choice only affects the backend owners.
- **Development speed.** FastAPI derives request validation and the OpenAPI schema from
  Pydantic models, and `packages/api-types` is generated from that schema. So the web app and
  the scanner get typed clients without hand-written API code. Async SQLAlchemy plus asyncpg
  lets one process serve the API, the order-expiry sweep and email delivery.
- **Data-model requirements.** The SRS model (§6) is relational: orders → items → tickets,
  inventory counters, promo limits, check-ins, audit. The hard rules have to hold under
  concurrency: no overselling (§4.3), atomic promo limits (§7), one check-in per ticket
  (§4.8), an append-only audit log (§4.16). PostgreSQL enforces them with row locks, CHECK
  constraints, partial unique indexes and a trigger (`tests/constraints/`). We'd have to
  rebuild much of that by hand on MongoDB. Integer KZT (`BigInteger`) and TIMESTAMPTZ come
  for free.
- **Deployment complexity.** Two official images (`postgres:16-alpine`, the API's Python
  image) plus the web app in one `docker compose up` (SRS §8). One backend, no
  microservices (§9). Alembic migrations run on start.

## Adding currencies and languages later (SRS §7)

SRS §7: "The architecture should support additional currencies and languages in future
releases." Today everything is KZT and kk / ru / en. This is how each would grow.

**A new language** needs no code change outside the message files:
1. Web: add `apps/web/messages/<locale>.json` with every key and add the locale to
   `src/i18n/routing.ts`. `npm run lint` fails until its keys match kk / ru / en
   (`scripts/check-messages.mjs`), and `scripts/check-hardcoded.mjs` keeps text out of
   components.
2. Scanner: add `apps/scanner/src/locales/<locale>.json` and register it in the i18n setup;
   `npm run lint -w @biletflow/scanner` checks the keys.
3. API: emails, notifications and PDF tickets read their text from per-locale templates.
   `test_every_template_exists_in_kk_ru_en_with_the_same_placeholders` and
   `test_document_strings_have_the_same_keys_in_every_locale` name every locale, so add it
   there. Users already store `locale`, and unknown locales fall back to Kazakh.

**A new currency** is a deliberate model change, because money columns are named `*_kzt` on
purpose (whole tenge, never floats; `money_kzt()` in `app/models/base.py`):
1. Add a `currency` column (ISO 4217) to `Event` and `TicketType`, with a new Alembic
   migration that defaults existing rows to `KZT`. `Order`, `Payment` and `Refund` already
   have a `currency` column (default `KZT`). Keep amounts as integers in the currency's
   minor unit.
2. Rename the `*_kzt` columns to `*_minor` in the same migration, and replace `money_kzt()`
   with a `money_minor()` helper. Totals, discounts and refunds stay per order, so an order
   never mixes currencies.
3. Read the display currency from the event instead of the `CURRENCY` setting, and format it
   with the locale (`useMoney()` in the web app, the PDF and email renderers).
4. Payout reporting groups by currency; it never sums across currencies.

Nothing in the MVP blocks this. The `CURRENCY` setting, the existing `currency` columns and
the locale-aware money formatting are the seams.

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
- **One promo code per campaign.** The schema allows several, but SRS 4.14 asks for "a unique
  promo code" per campaign, so the API creates exactly one with it. Codes are unique across
  BiletFlow regardless of case (`uq_promo_codes_code_lower`).
- **Discount rounding.** A percentage rounds down to whole KZT on each order line. A fixed-KZT
  discount is capped at the eligible subtotal and split across eligible lines in proportion to
  their value, with the rounding remainder on the last line.
- A campaign's discount and eligible ticket types can't change after creation, so earlier
  orders stay explainable. Its name, dates and redemption limit can (not below what's used).
- A paid ticket type discounted to 0 KZT still needs paid-sales activation; the order is then
  confirmed at once like a free one.
- A Campaign QR resolves to its event even when the campaign can't be used; the page opens
  without the code and says why.
- **Notifications are rendered once, in the account language**, when they're created. The
  in-app copy keeps that text even if the user switches the UI language later, so the inbox
  always matches the email that was sent.
- **"Event update" means the time, venue or title** of a published or unpublished event. Other
  edits (description, cover, capacity) don't notify anyone. Ticket holders are buyers with a
  valid or checked-in ticket, notified once each however many tickets they hold.
- `notifications.action_path` (migration 0002) stores the web path an in-app notification
  links to, because support cases have no column on the table to derive it from.
- **Rate limits** are in-process (single API worker) and keyed by IP and by email; the email
  limit counts every attempt so a 429 doesn't reveal registration. Limits: login 20/min/IP and
  5/min/email; register 5/10 min/IP; account emails 5/15 min/IP and 3/15 min/email.
- **Event history.** "Completed" includes events whose end time has passed. Completed and
  cancelled events are read-only, but refunds still work. The timeline is visible to the
  organizer, event admins and Platform Admins (not check-in staff). Duplicating copies
  configuration only (not campaigns, whose codes are unique, nor paid-sales activation, which is
  per event) and moves a past event forward by whole weeks.
- **Analytics definitions.** Order figures use orders *confirmed* in the date range, per order
  line (so the ticket-type filter is exact). Refunded orders count in gross and again under
  refunds; the chart and per-type figures show only sales that stand. Processing fees are
  estimated per line at `PROCESSING_FEE_BPS`. Capacity and attendance are the current state.
  Default range: last 30 days; days are cut in the event's time zone (SRS §12 "default date
  ranges and chart formats": daily line chart, horizontal bars by ticket type).
- **Admin portal.** `event_reports` and `platform_settings` are new tables (migrations 0003,
  0004). The activation fee is read from `platform_settings` when an admin has set it, else from
  `ACTIVATION_FEE_KZT`; a change applies to fees paid afterwards only. Platform Admins can't be
  suspended through the portal. Suspensions require a reason. Suspending an event keeps issued
  tickets valid (attendees may still be admitted) but stops sales and hides it from the listing.
- **Support cases.** Attendee cases are answered by the event's organizer and its event admins
  (check-in staff don't do support); organizer cases by Platform Admins, who can also open any
  attendee case for escalation. An attendee case always has an event, derived from the order
  or ticket. A requester's reply reopens a waiting or resolved case. No attachments (SRS §12).
- **Refunds are full and organizer-only** (SRS 4.9 "full refunds", "authorized organizers").
  Event admins can't refund. Refunded and cancelled tickets go back on sale unless the event is
  cancelled. A promo redemption stays counted after a refund (it was used).
- Cancelling an event cancels its valid tickets and pending orders and refunds every paid order
  in full, each with the fixed idempotency key `event-cancel:<order id>`.
