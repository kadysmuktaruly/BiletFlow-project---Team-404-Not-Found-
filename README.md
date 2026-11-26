# BiletFlow

Self-service event ticketing for Kazakhstan. Organizers create events, sell general-admission
or assigned-seat tickets in KZT, run promo campaigns, and check attendees in at the door with a
QR scanner. Attendees buy tickets, receive them by email, and can open support cases.

> **Status:** early development. The data model, accounts and sign-in, organizer profiles and
> draft events are in place in the API and the web app. Ticketing, checkout, check-in and
> the scanner app follow; see [`docs/plan-reports-3-4.md`](docs/plan-reports-3-4.md).
> Section references like "SRS 4.3.1" throughout the code point to the project's Software
> Requirements Specification.

## What the platform does

| Area | Summary |
|---|---|
| **Accounts and roles** | Attendee, Organizer, Event Admin (delegated by an organizer for one event), Platform Admin. Check-in staff are assigned per event. |
| **Events** | Draft → published / unpublished / cancelled / completed. Visibility can be public, unlisted, or private. Each event stores an IANA timezone so calendar exports keep the correct local time. |
| **Tickets and seating** | General admission, or assigned seating built from venue → section → row → seat. Seats are held for a limited time during checkout (`SEAT_HOLD_TTL_SECONDS`, 10 minutes by default). |
| **Orders and payments** | Orders, attendees, tickets, payments, and refunds. All money is stored as whole KZT integers. Payments and refunds use idempotency keys. |
| **Paid sales activation** | Organizers pay a one-time fee (`ACTIVATION_FEE_KZT`) per event and set up a payout account before they can sell paid tickets. Platform admins can suspend paid sales. |
| **Promotions** | Campaigns with percentage or fixed-KZT discounts, case-insensitive promo codes, per-ticket-type restrictions, and redemption limits. |
| **Check-in** | By QR scan or manual attendee search, with every check-in recorded. |
| **Support and notifications** | Support cases with categories and status tracking. Email and in-app notifications. |
| **Audit log** | An append-only record of sensitive actions. |

## Repository layout

```
biletflow/
├── apps/
│   ├── api/                    # FastAPI backend (Python 3.12, async SQLAlchemy)
│   │   ├── app/
│   │   │   ├── config.py       # Settings read from environment / .env
│   │   │   ├── deps.py         # Auth and permission dependencies
│   │   │   ├── models/         # user, event, seating, order, campaign, support, audit
│   │   │   ├── routers/        # Thin HTTP layer under /api/v1
│   │   │   ├── schemas/        # Request and response models
│   │   │   ├── services/       # Business logic
│   │   │   └── i18n/           # Email strings in kk / ru / en
│   │   ├── migrations/         # Alembic (async); 0001_initial_schema.py
│   │   └── tests/              # pytest + httpx on a throwaway *_test database
│   ├── web/                    # Next.js app (App Router, Tailwind, next-intl)
│   │   ├── messages/           # Every user-facing string, in kk.json / ru.json / en.json
│   │   └── src/
│   └── scanner/                # Expo app for Event Admins (expo-router, expo-camera)
│       └── src/locales/        # kk.json / ru.json / en.json
├── packages/api-types/         # TypeScript types generated from the API's OpenAPI schema
├── scripts/gen-api-types.sh    # Regenerates packages/api-types
├── docs/                       # SRS, decisions, plans, demo scripts
├── docker-compose.yml          # db, api, web, mailpit (with health checks)
└── .env.example                # All environment variables, documented
```

## Tech stack

- **API:** FastAPI, Pydantic v2, SQLAlchemy 2.0 (async only), asyncpg, Alembic
- **Database:** PostgreSQL 16
- **Web:** Next.js 16 (App Router, TypeScript, Tailwind CSS), next-intl, openapi-fetch
- **Scanner:** Expo SDK 58 (React Native, TypeScript), expo-router, expo-camera, i18next
- **Tooling:** [uv](https://docs.astral.sh/uv/), Ruff, mypy (strict), pytest, npm workspaces

## Getting started

Requirements: Docker with at least 2 GB of memory. For development
outside Docker you also need [uv](https://docs.astral.sh/uv/) and Node.js 22.

```bash
cp .env.example .env        # optional; the defaults work
docker compose up -d --build
docker compose ps           # wait for db, api, web and mailpit to be "healthy"
```

By default the web container runs `next dev`, which fits a 2 GB Docker VM; each page compiles
the first time you open it. For the demo, run the production build instead (it needs a Docker
VM with at least 4 GB):

```bash
WEB_BUILD_TARGET=runtime docker compose up -d --build
```

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API and OpenAPI docs | http://localhost:8000/docs |
| Mailpit (every email the app sends) | http://localhost:8025 |
| Postgres | `localhost:5433` |

The API applies migrations and loads demo data on start (`SEED_DEMO_DATA=true`). The data
covers a free student meetup, a paid KZT jazz night with a 15% campaign (code `JAZZ15`), a
promo purchase, a refunded order, a check-in, a support case, and a past event for the history
views. The accounts are organizer, three attendees (`attendee@`, `aliya@`, `timur@`), an Event
Admin (`staff@`) and a Platform Admin (`admin@`), all at `demo.biletflow.kz`, all with the
password `Demo-pass-2026`. See [`apps/api/app/seed.py`](apps/api/app/seed.py) and the
walkthrough in [`docs/demo-report-3.md`](docs/demo-report-3.md).

To run the API on the host instead:

```bash
docker compose up -d db mailpit
cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

`DATABASE_URL` must use the async driver (`postgresql+asyncpg://...`). A plain `postgresql://`
URL will fail, because the app never opens a sync session.

## Development

Run these from `apps/api`:

```bash
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy .              # strict type checking
uv run pytest              # tests
uv run alembic check       # confirm the models and migrations match
```

### Web app

Requirements: Node.js 22. JavaScript workspaces use npm.

```bash
npm install                        # from the repo root
npm run dev -w @biletflow/web      # http://localhost:3000 (needs the API on :8000)
npm run lint -w @biletflow/web     # eslint + checks kk/ru/en have the same message keys
npm run typecheck --workspaces --if-present
```

Every user-facing string lives in `apps/web/messages/{kk,ru,en}.json`; nothing is
hard-coded in components. API errors are shown by translating their `error.code` under
`errors.*`. The app talks to the API through a typed client (`src/lib/api.ts`). The access
token is kept in memory, and the refresh token is the httpOnly cookie set by the API.

### Scanner app

The check-in app for Event Admins. It's in the same npm workspace, so `npm install` at the
root covers it.

```bash
# The phone can't reach "localhost" on your laptop: use the laptop's LAN IP.
echo "EXPO_PUBLIC_API_BASE_URL=http://192.168.1.20:8000" > apps/scanner/.env.local
npm run start -w @biletflow/scanner      # scan the QR with Expo Go
npm run lint -w @biletflow/scanner       # expo lint + kk/ru/en key check
npm test -w @biletflow/scanner           # jest (jest-expo)
```

After sign-in, the scanner lists only the events you organize or are assigned to as staff
(`GET /checkin/events`). Tapping one opens the camera, which reads QR codes only, with the live
"checked in of registered" count on top (refreshed every 10 seconds). Each scan goes to the API
(`POST /checkin/events/{id}/scan`), which checks the signature and the ticket's live status and
records the check-in once, even if two phones scan the same ticket. Results use color, a symbol
and text for all five states: valid, invalid, cancelled, refunded, already used. An invalid
result says why (not a BiletFlow ticket, another event's ticket, or a promo QR code), and an
already-used one says when it was checked in (event time zone).

**Search attendees** finds a ticket by name, email or ticket number when its QR won't scan, and
checks it in with the same call. Owners and event admins see **Undo check-in** (with a
confirmation) after a valid result; check-in staff don't. "Preview result screens" shows all five
states for training; nothing is recorded there.

The scanner sends `X-Client: scanner`, so the API returns the refresh token in the response
body. The app keeps it in the OS keychain or keystore (`expo-secure-store`). The camera is
used only to read QR codes. Its strings live in `apps/scanner/src/locales/`, and the app uses
the device language when it's kk, ru or en, otherwise Kazakh.

### API types

`packages/api-types` is generated from the FastAPI OpenAPI schema. Never edit it by hand.
After changing an endpoint or schema, run:

```bash
npm run gen:api-types              # from the repo root; needs uv and npm install
```

CI fails if the committed types don't match the API.

### Tests

`uv run pytest` needs the Compose database running (`docker compose up -d db`). It never
touches the dev database: the harness (`tests/conftest.py`) drops and recreates
`<name>_test` on the same server at the start of each run, migrates it with Alembic, and
truncates every table before each database test. Tests talk to the app over httpx, and
concurrency tests send real parallel requests, so Postgres sees concurrent transactions.

### Verifying database constraints

The most important guarantees are enforced by Postgres itself, not by application code.
`tests/constraints/verify_constraints.sql` checks them, and `tests/test_constraints_sql.py`
runs that script against the test database as part of `uv run pytest`. See
[`apps/api/tests/constraints/README.md`](apps/api/tests/constraints/README.md) for what each
check covers.

### End-to-end test (Playwright)

`apps/web/e2e/core-flow.spec.ts` runs the SRS 13.4 core flow in Chromium against a running
stack with the demo seed:

1. The organizer creates a campaign.
2. The attendee opens its Campaign QR link, sees the code applied, and buys a ticket with the
   DEMO payment.
3. The confirmation shows the discount, the PDF downloads, and a support case opens from the
   order.
4. At the door the ticket is admitted once, then `already_used`, and the Campaign QR is
   rejected.
5. The organizer's analytics count the redemption.

```bash
docker compose up -d                      # the stack, with demo data
npx playwright install chromium           # once
npm run e2e -w @biletflow/web             # E2E_BASE_URL / E2E_API_URL to point elsewhere
```

Running it again within a minute can hit the login rate limit (5 sign-ins per email per
minute). Wait a minute, or run the API with `RATE_LIMIT_ENABLED=false` as CI does.

### Continuous integration

`.github/workflows/ci.yml` runs on every pull request, whatever its base branch:

- **API:** ruff check, ruff format --check, strict mypy, `alembic upgrade head`,
  `alembic check`, and pytest against a Postgres 16 service.
- **Web:** eslint, the kk/ru/en key check, `tsc` for every workspace, and a production build.
- **Scanner:** `expo lint`, the kk/ru/en key check, `tsc`, and jest.
- **API types:** regenerates `packages/api-types` and fails if it differs from what's committed.
- **No secrets:** `scripts/check-secrets.py`.
- **End-to-end:** migrates and seeds a fresh database, starts the API and the production web
  build, and runs the Playwright core flow in Chromium. On failure it keeps the report, traces
  and server logs as an artifact.

### Project documents

- [`docs/srs/`](docs/srs/srs.md): the SRS (v0.3 PDF, plus a searchable text copy)
- [`docs/decisions.md`](docs/decisions.md): SRS §12 decisions and the assumptions the code
  relies on
- [`docs/plan-reports-3-4.md`](docs/plan-reports-3-4.md): build plan for Reports 3 and 4

## API

The API is served under `/api/v1`. Interactive OpenAPI docs are at
http://localhost:8000/docs when the stack is running. Every error uses one shape:
`{"error": {"code", "message", "details"}}`, where `code` is a stable identifier that
clients translate.

### Accounts and sign-in (SRS 4.1)

| Endpoint | Purpose |
|---|---|
| `POST /auth/register` | Create an `attendee` or `organizer` account and email a verification link. `platform_admin` cannot be self-assigned. |
| `POST /auth/verify-email` | Confirm the email with the token from that link. The first confirmation also signs the user in; opening the link again only confirms. |
| `POST /auth/resend-verification` | Send the link again. |
| `POST /auth/login` | Returns a 15-minute access token. An account must confirm its email first (`email_not_confirmed`, checked only after the password matches). Browsers get the refresh token as an httpOnly `bf_refresh` cookie; clients sending `X-Client: scanner` get it in the body. |
| `POST /auth/refresh`, `POST /auth/logout` | Rotate the session, or clear the cookie. |
| `POST /auth/forgot-password`, `POST /auth/reset-password` | Email a single-use reset link, then set a new password. Resetting signs out every other session. |
| `GET /me`, `PATCH /me` | The signed-in user. Name, phone and language can be changed; role and email cannot. |
| `DELETE /me` | Delete your account with your current password (web: `/account`). Not an SRS requirement. The row is anonymised, not removed, because orders, tickets and the audit trail reference it: name, email, phone and password are replaced, every session ends, and the email can register again. Platform Admins can't (409 `cannot_delete_admin`); organizers must first cancel or finish published events (409 `organizer_has_live_events`). |

Register, resend-verification, forgot-password and login never reveal whether an email is
registered. Passwords are hashed with Argon2. In development every email lands in Mailpit at
http://localhost:8025.

Role checks are reusable dependencies in `app/deps.py` (`CurrentUser`, `require_role`,
`OrganizerUser`, `PlatformAdminUser`). Being an Event Admin is a per-event
`StaffAssignment`, not a platform role.

### Organizers and events (SRS 4.1, 4.2)

| Endpoint | Purpose |
|---|---|
| `GET/PUT /organizer/profile` | Contact details. The profile is created when an organizer registers. |
| `GET/PUT /organizer/payout-account` | **DEMO** payout account. Only the last four digits are accepted and stored, and verification is simulated. |
| `POST /organizer/events` | Create a draft. The server generates the slug and sets the owner and status. |
| `GET /organizer/events`, `GET/PATCH /organizer/events/{id}` | List, read and edit your own events. Cancelled and completed events are read-only. |

Event times can be sent with a UTC offset, or without one. A time without an offset is read as
local time in the event's IANA `timezone` (for example `Asia/Almaty`). Responses include
`starts_at` (UTC) and `starts_at_local` (the event's own zone). Someone else's event returns
404, not 403.

### Ticket types, orders and tickets (SRS 4.3, 4.4, 4.6, 4.7)

| Endpoint | Purpose |
|---|---|
| `GET/POST /organizer/events/{id}/ticket-types`, `PATCH/DELETE …/{ticket_type_id}` | Free (`price_kzt: 0`) or paid types with quantity, sales window, per-order limit and `is_hidden`. Responses include available, reserved, sold, refunded and checked-in counts. A type that has orders can be hidden but not deleted. Price and quantity changes are written to the audit log. |
| `POST /orders` | Send ticket type ids and quantities (and optionally one attendee per ticket). The server computes every amount. A zero-total order is confirmed at once and its tickets issued. A paid order is `awaiting_payment` and holds its tickets for `ORDER_RESERVATION_TTL_SECONDS`. |
| `GET /orders/{id}`, `GET /me/orders` | Your orders. Other people's orders return 404. |
| `GET /me/tickets`, `GET /me/tickets/{id}/qr.svg` | Your tickets and their QR codes. |
| `GET /me/tickets/{id}/pdf` | The ticket as a print-optimized A4 PDF (SRS 4.7), in your account language. |

**Inventory never oversells.** Checkout locks the event row, then reserves with a conditional
`UPDATE … WHERE sold + reserved + n <= total`. `ck_ticket_types_inventory_within_total` backs
it up. `tests/test_inventory_concurrency.py` fires concurrent requests at the last ticket and
expects exactly one sale. Unpaid orders expire; the next checkout for the event releases them,
and a background sweep (`ORDER_SWEEP_INTERVAL_SECONDS`) cleans up the rest.

**Ticket QR codes** carry `BFT1.<ticket id>.<HMAC-SHA256>`, signed with
`TICKET_SIGNING_SECRET`. The token identifies the ticket only. Its status is always read live
at check-in, so a refunded ticket's QR code stops working.

### DEMO payments and paid-sales activation (SRS 3.2, 4.5, 4.6)

Every payment is simulated. No real money moves. Payment records have `is_simulated: true`,
API responses carry `"demo": true`, and emails and screens say DEMO.

| Endpoint | Purpose |
|---|---|
| `POST /orders/{id}/payments` | Body `{"outcome": "succeed" \| "fail"}` plus an `Idempotency-Key` header. `succeed` confirms the order, issues the tickets and emails them with QR codes. `fail` releases the tickets and emails a DEMO failure notice. |
| `POST /orders/{id}/abandon` | Leave the payment step. The tickets go back on sale at once rather than at expiry. |
| `GET /organizer/events/{id}/activation` | The paid-sales checklist: a paid ticket type, the simulated identity check, a connected payout account, the activation fee and the terms. |
| `POST …/activation/identity`, `…/payout-account`, `…/terms` | Body `{"confirm": true}`. No identity documents are collected. |
| `POST …/activation/fee-payment` | Pays `ACTIVATION_FEE_KZT` (non-refundable) through the same DEMO provider, with the same `Idempotency-Key` rules. |

**Idempotency.** The key is stored per user in `payments.idempotency_key` (unique). Repeating a
request returns the original result (`200`, `replayed: true`) and never charges twice, even
when the retries arrive at the same moment (`test_concurrent_retries_with_one_key_charge_once`).
Reusing a key for a different order returns `409 idempotency_key_reused`.

**Paid checkout is blocked** (`409 paid_sales_not_active`) until the event's checklist is
complete, or while a Platform Admin has suspended it. Free registration never needs activation.

**Processing charges** (`PROCESSING_FEE_BPS`, 3% by default) are recorded on the order for the
organizer's estimated payout. They are never added to what the attendee pays.

**Emails** (all in Mailpit during development): verification, password reset, order
confirmation with an inline QR image per ticket (free and paid), and DEMO payment failure.

### Organizer event management (SRS 4.2, 4.5, 4.8)

| Endpoint | Purpose |
|---|---|
| `POST /organizer/events/{id}/publish` | Needs a verified email, a venue, a visible ticket type and a future end time. |
| `POST /organizer/events/{id}/unpublish` | Hides the page and pauses registration. Issued tickets stay valid. |
| `POST /organizer/events/{id}/cancel` | Cancels every valid ticket (they fail at the door) and releases unpaid orders. Refunds arrive with SRS 4.9. |
| `PATCH /organizer/events/{id}` | Also sets `visibility` (`public`, `unlisted`, `private`), the registration window and `capacity` (across all ticket types). |
| `GET /organizer/events/{id}/preview` | The public page as attendees will see it, whatever the status. |
| `GET/POST /organizer/events/{id}/staff`, `DELETE …/{assignment_id}` | Assign existing users as `event_admin` (can undo check-ins) or `check_in_staff` (scan only). |
| `GET /events`, `GET /events/{slug}` | Public pages. Only published, public, upcoming events are listed. Unlisted events open by link. Private events open only for their organizer and staff (404 for everyone else). |

Publishing, unpublishing, cancelling, capacity and visibility changes, and staff changes are
written to the audit log.

In the web app, each event has its own area at `/organizer/events/{id}`, with tabs for details
(including visibility, registration window and capacity), ticket types with live counts, the
paid-sales checklist (DEMO), staff, and a preview, plus Publish, Unpublish and Cancel.

### Check-in (SRS 4.8)

For the scanner app. Every endpoint below needs the event's owner or an active staff
assignment; anyone else, including a Platform Admin, gets 404.

| Endpoint | Purpose |
|---|---|
| `GET /checkin/events` | Events you organize or are assigned to. |
| `POST /checkin/events/{id}/scan` | Body `{"payload": "<raw QR text>"}`. Always 200 with `result`: `valid`, `invalid`, `cancelled`, `refunded` or `already_used`, the ticket (number, attendee, type, status) and live counts. |
| `POST /checkin/events/{id}/tickets/{ticket_id}/check-in` | The same check-in for a ticket found by manual search. |
| `POST /checkin/events/{id}/tickets/{ticket_id}/undo` | Owners and event admins only (`403 checkin_undo_forbidden` for check-in staff). The ticket is valid again; the reversal stays in the history and the audit log. |
| `GET /checkin/events/{id}/stats` | `registered` (valid plus checked-in tickets) and `checked_in`. |
| `GET /checkin/events/{id}/attendees?q=` | Manual search by attendee name, email or ticket number, case-insensitive, up to 50 results. |

**One admission per ticket.** A check-in is one conditional
`UPDATE tickets … WHERE status = 'valid'`, so when two devices scan the same ticket at the same
moment, exactly one gets `valid` and the other `already_used`
(`tests/test_checkin.py::test_double_scan_concurrent_one_checkin`). `uq_checkin_active_ticket`
backs it up in the database.

**Status is read live.** The QR token only names the ticket, so a ticket cancelled or refunded
after it was emailed fails at the door. `invalid` comes with a `reason`: `unrecognized` (not a
BiletFlow ticket, or a bad signature), `wrong_event`, or `campaign_qr_not_admission`. A Campaign
QR (`BFC1.…`, or a `/c/BFC1.…` link) is never accepted as a ticket.

Check-ins and reversals are written to the audit log for the event timeline (SRS 4.16).
`test_checkin_under_2s` checks the two-second target (SRS 7) for 30 scans.

### Promo codes and Campaign QR codes (SRS 4.14)

| Endpoint | Purpose |
|---|---|
| `GET/POST /organizer/events/{id}/campaigns` | List or create campaigns. Each campaign has one promo code (yours, or generated) and an opaque Campaign QR link `PUBLIC_BASE_URL/c/BFC1.…`. Percentage (1–100) or fixed-KZT discount, optional validity dates, redemption limit and eligible ticket types. |
| `GET/PATCH /organizer/events/{id}/campaigns/{campaign_id}` | One campaign with its report: redemptions, orders, tickets sold, gross revenue, discount and net revenue. Name, dates and limit can change; the discount and eligible types can't. |
| `POST …/campaigns/{campaign_id}/disable` | New checkouts get `promo_disabled`; placed orders keep their discount. |
| `POST /promo/validate` | Preview: the code, the discount and the new total for the chosen tickets. No sign-in needed. |
| `GET /campaigns/resolve/{token}` | Where a Campaign QR leads: the event slug and, if the campaign can be used, its code. |
| `POST /orders` with `promo_code` | Applies the code at checkout. |

**The server computes every discount.** Clients send only a code. Codes are case-insensitive and
unique across BiletFlow. A percentage rounds down to whole KZT per line; a fixed amount is capped
at the eligible subtotal and split across eligible lines. A rejected code fails with a clear
`error.code`: `promo_not_found`, `promo_disabled`, `promo_not_started`, `promo_expired`,
`promo_exhausted` or `promo_not_applicable`.

**The limit holds under concurrency.** Checkout takes a redemption with one conditional
`UPDATE … WHERE redeemed_count < max_redemptions`; `ck_promo_codes_within_limit` backs it up
(`tests/test_promotions.py::test_promo_limit_holds_under_concurrency`). An order awaiting payment
holds its redemption and gives it back if it fails, expires or is abandoned.

Campaign tokens (`BFC1.`) and admission tokens (`BFT1.`) never overlap, and check-in rejects
Campaign QR codes. Creating, changing and disabling a campaign is written to the audit log.

### PDF tickets and Campaign QR images (SRS 4.7, 4.14)

**PDF ticket** (`GET /me/tickets/{id}/pdf`, also attached to every confirmation email): one A4
page with the event, date and time in the event's time zone, venue, ticket type, attendee, seat
when assigned, ticket number, status and the QR code. It has **no price or payment data**. The QR
is the same admission token as the digital ticket, so both copies are one ticket and one
admission. It's 70 mm, error correction M, black on white with a 4-module quiet zone, drawn as
vectors. `tests/test_documents.py` renders the PDF in grayscale at 72, 150 and 300 dpi and
decodes it with zxing.

**Campaign QR** (`GET /organizer/events/{id}/campaigns/{campaign_id}/qr.svg` or `qr.pdf` for an
A5 poster, `?lang=kk|ru|en`): dark-purple modules in a dashed purple frame under a
"PROMO · NOT A TICKET" banner. It encodes only the campaign link.

Text uses the bundled DejaVu Sans (`app/assets/fonts/`, free licence in `DejaVu-LICENSE.txt`),
which covers Kazakh and Russian. PDFs are built with reportlab.

### Notifications (SRS 4.10)

Every feature tells users things through one call, `app.services.notifications.notify(session,
user, Message(...))`. It renders a template from `app/i18n/emails.py` in the user's language
(kk, ru or en) and writes an **email** (sent after commit, tracked as pending → sent or
failed) and an **in-app** copy with a link. Both say the same thing.

| Trigger | Template | Who |
|---|---|---|
| Account verification | `verify_email` | the new user (email only) |
| Registration or purchase confirmation, ticket delivery | `order_confirmed` (with QR images and PDFs) | buyer |
| DEMO payment failure | `payment_failed` | buyer |
| Event update (time, venue or title of a published event) | `event_updated` | ticket holders, once each |
| Event cancellation | `event_cancelled` | ticket holders |
| Refund completed, registration cancelled | `refund_completed`, `registration_cancelled` | buyer (sent by refunds, SRS 4.9) |
| Payout account status (DEMO) | `payout_status` | organizer |
| Support: new message, assignment, status change | `support_*` | case participants (SRS 4.13) |

| Endpoint | Purpose |
|---|---|
| `GET /me/notifications?unread_only=&limit=` | In-app inbox, newest first, with `unread_count`. |
| `GET /me/notifications/unread-count` | For the header badge. |
| `POST /me/notifications/{id}/read`, `POST /me/notifications/read-all` | Mark read. Someone else's notification is 404. |

The web header shows **Notifications** with the unread count (polled every minute), and
`/notifications` lists them with links and "Mark all as read".

### Orders, refunds and cancellations (SRS 4.9)

| Endpoint | Purpose |
|---|---|
| `GET /organizer/events/{id}/orders?q=&status=` | The event's orders with buyer, totals, refunds and `can_refund` / `can_cancel`. |
| `POST /organizer/events/{id}/orders/{order_id}/refund` | **DEMO** full refund of a paid order, with an `Idempotency-Key` (a repeat returns the first refund, 200 `replayed: true`). |
| `POST /organizer/events/{id}/orders/{order_id}/cancel` | Cancel a free registration. |
| `PATCH /organizer/events/{id}` with `refund_policy` | The refund policy shown on the event page. |

Refunded or cancelled tickets stop working at the door at once and go back on sale. Every refund
and cancellation is written to the audit log and the buyer is notified. **Cancelling an event
refunds every paid order in full**, with a fixed key per order so it can never refund twice.
Only the event's organizer can refund. The web app has **My orders** for attendees and an
**Orders** tab for organizers, where refunds and cancellations sit behind a confirmation.

### Support cases (SRS 4.13)

| Endpoint | Purpose |
|---|---|
| `POST /support/cases` | Open a case. `attendee` cases come from an event, order or ticket (the server derives the event and checks they're yours) and go to the event's organizer and event admins. `organizer` cases go to Platform Admins. No attachments. |
| `GET /support/cases`, `GET /support/cases/{id}` | Cases you opened and cases you handle; one case with its thread. Poll them; there are no sockets. |
| `POST /support/cases/{id}/messages` | Reply. Staff can add `internal` notes the requester never sees. A requester's reply moves a waiting case to In progress and a resolved one back to Open. |
| `PATCH /support/cases/{id}` | Staff only: status (Open, In progress, Waiting for customer, Resolved) and assignee. |

A case you aren't part of returns **404**. New messages, assignments and status changes notify
the other side by email and in-app; status changes go on the event's audit timeline. On the
web: **Get help** on event, order and ticket pages, **Contact BiletFlow support** for
organizers, and **Support** in the header, with the thread refreshing every 10 seconds.

### Platform administration (SRS 4.12)

Platform Admins only (403 for anyone else). Every change is written to the audit log.

| Endpoint | Purpose |
|---|---|
| `GET /admin/summary` | Counts for the overview. |
| `GET /admin/users`, `POST /admin/users/{id}/suspend` / `unsuspend` | Search; suspend (with a reason) or reinstate. A suspended user's sessions stop working at once. |
| `GET /admin/events`, `POST /admin/events/{id}/suspend` / `unsuspend` | Suspending stops all sales on the next request and hides the event; issued tickets stay valid. |
| `POST /admin/events/{id}/paid-sales/suspend` / `resume` | Stop paid checkout and payment only (fraud suspected). |
| `GET /admin/activations`, `/admin/orders`, `/admin/payments` | Paid-sales activation records, orders and DEMO payments (filter failed or refunded). |
| `GET /admin/reports`, `POST /admin/reports/{id}/review` | Reported events: dismiss, or suspend the event. |
| `GET/PUT /admin/settings` | The activation fee. With no saved value, `ACTIVATION_FEE_KZT` applies. A change affects fees paid from then on. |
| `GET /admin/export/{users,events,orders,payments}.csv` | CSV, up to 10,000 rows; formula-like cells are escaped. |
| `POST /events/{slug}/report` | Any signed-in user reports an event (one open report each). |

The web portal is at `/admin` (header link **Admin**), with tabs for each area, and
suspensions behind a confirmation that requires a reason. Event pages have **Report this
event**. Two tables arrived with it: `event_reports` (migration 0003) and `platform_settings`
(0004).

### Organizer analytics (SRS 4.15)

`GET /organizer/analytics?event_id=&ticket_type_id=&date_from=&date_to=`: your events only.
The date range defaults to the last 30 days in the event's time zone (Asia/Almaty across
several events), at most a year.

- **Capacity:** capacity, sold, remaining, % sold (current state).
- **Revenue (DEMO):** tickets sold and refunded, gross, discounts, refunds, net, processing
  fees and estimated payout, for orders confirmed in the range.
- **Sales over time:** one point per day. **By ticket type:** sold in range, revenue, sold
  overall, capacity, checked in.
- **Campaigns:** redemptions, orders, tickets, gross, discount, net.
- **Attendance:** issued, checked in, absent, % checked in (current state).

It runs in a read-only, time-boxed transaction, so it can't hold up checkout
(`test_analytics_never_holds_up_checkout`). The web dashboard is at **Analytics** in the
organizer menu and on each event's **Analytics** tab: KPI tiles, a line chart of sales over
time (tickets or revenue, never both on one axis), a bar chart by ticket type, and a table
view for every chart. Charts use recharts.

### Event history and duplication (SRS 4.16)

- Every event has a `phase`: **upcoming**, **active**, **completed** (ended, or marked
  completed) or **cancelled**. `GET /organizer/events?phase=` filters by it; **My events** has a
  tab for each.
- **Past and cancelled events are read-only**: edits, ticket types, campaigns and cancelling
  return `409 event_not_editable`. Their orders, tickets, attendees, check-ins, campaigns,
  support cases and analytics stay available, and refunds still work.
- `GET /history/events/{id}/timeline?date_from=&date_to=&category=`: the activity timeline
  from the append-only audit log (time, who, action, entity, description), for the event's
  organizer, its event admins and Platform Admins (404 for anyone else). Each event has a
  **History** tab.
- `POST /organizer/events/{id}/duplicate`: a new draft with the same details, venue,
  visibility, capacity, refund policy and ticket types. It never copies orders, tickets,
  payments, check-ins, support cases, campaigns or paid-sales activation. A past event's dates
  move forward by whole weeks (same weekday and time). The **Duplicate** button is on every
  event.

### Hardening (Report 6)

- **Rate limiting** on `POST /auth/login` (20 per minute per client IP, 5 per minute per
  email), `/auth/register` (5 per 10 minutes per IP), and `/auth/forgot-password` and
  `/auth/resend-verification` (5 per 15 minutes per IP, 3 per email). Over the limit you get
  `429 rate_limited` with `Retry-After`. The per-email limit counts attempts whether or not the
  address is registered, so it reveals nothing. It's in-process (`app/ratelimit.py`), which is
  exact for the single API process Compose runs. Off under `ENVIRONMENT=test` unless
  `RATE_LIMIT_ENABLED` is set.
- **No secrets in the repository:** `python3 scripts/check-secrets.py` scans tracked files for
  private keys, tokens and secrets in env files, and fails if a `.env` is tracked. CI runs it
  on every PR. Production refuses to start with the development secrets.
- **Backups:** `scripts/backup-db.sh` writes a compressed `pg_dump` to `backups/` (git-ignored).
  `scripts/restore-db.sh <dump> <database>` restores it into another database to check it, or
  over the main one with `--yes` (stop `api` first).
- **HTTPS:** proposed, not added yet. See
  [`docs/https-proxy-proposal.md`](docs/https-proxy-proposal.md).

### Attendee web pages (SRS 4.2, 4.4, 4.6, 4.7)

`/events` lists upcoming public events. `/events/{slug}` is the event page with ticket
selection, then attendee names (one per ticket). A free order is confirmed straight away. A
paid order goes to `/checkout/{orderId}`, the **DEMO payment** page: succeed, fail, or cancel
and release the tickets. `/orders/{orderId}` is the confirmation with QR codes, and `/tickets`
(**My tickets**) lists every ticket with its QR code and status. Checkout requires sign-in;
the event page sends visitors to sign in and brings them back.

**Promo codes on the web (SRS 4.14).** The event page has a promo code field. The server quotes
the discount for the chosen tickets and the panel shows the code, the discount and the new
total; checkout and the confirmation repeat them. A Campaign QR opens `/c/{token}`, which
resolves the campaign and forwards to the event with `?promo=CODE` (or explains why the code
can't be used). Tickets on the confirmation page and on My tickets have a **Download PDF**
button.

**Organizer: Campaigns and Attendees tabs.** Campaigns lists each campaign with its code,
discount, status, redemptions and DEMO sales report, a preview of its Campaign QR ("Promo, not
a ticket"), copy-link, SVG and A5-poster downloads, and Disable. New campaigns can be
percentage or fixed KZT, with optional dates (event time zone), limit and eligible ticket types.
Attendees lists every ticket with search (name, email, ticket number, order) and a status
filter (`GET /organizer/events/{id}/attendees`).

## Data model conventions

- **UUID primary keys** everywhere, generated both in Python and by the database (`gen_random_uuid()`).
- **Money is `BigInteger` whole KZT**, never a float or decimal (`price_kzt`, `total_kzt`, ...).
- **Every timestamp is `TIMESTAMPTZ`.** `Base.type_annotation_map` makes that the default.
- **Enums are native Postgres enums storing lowercase values.** Always build them with
  `pg_enum()` in `app/models/base.py`. The partial-index predicates compare against those
  lowercase values, so the uniqueness guarantees depend on it.

Key guarantees the database enforces:

| Constraint | Prevents |
|---|---|
| `uq_ticket_active_seat` | Selling one seat twice. Refunded or cancelled tickets release the seat. |
| `uq_seat_hold_active` | Two active holds on the same seat. |
| `ck_promo_codes_within_limit` | Redeeming a promo code more times than allowed, even under concurrency. |
| `ck_orders_discount_within_subtotal` | A discount larger than the order subtotal. |
| Append-only trigger on `audit_log_entries` | Editing or deleting audit history. |

Seat holds are only unique while `status = 'active'`. The expiry sweep is cleanup, so queries
that reserve seats must also check `expires_at` themselves.

## Configuration

All variables are documented in [`.env.example`](.env.example). The main ones:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://biletflow:biletflow@localhost:5433/biletflow` | Async Postgres connection |
| `POSTGRES_PORT` | `5433` | Host port for the Postgres container |
| `SEAT_HOLD_TTL_SECONDS` | `600` | How long a checkout seat hold lasts |
| `ORDER_RESERVATION_TTL_SECONDS` | `600` | How long an unpaid order holds its tickets |
| `TICKET_SIGNING_SECRET` | dev key | Signs ticket QR codes; required outside development |
| `ACTIVATION_FEE_KZT` | `5000` | Paid sales activation fee (placeholder amount, non-refundable) |
| `PROCESSING_FEE_BPS` | `300` | Processing charge taken from the organizer's payout (DEMO) |
| `CURRENCY` | `KZT` | Currency for the initial release |
