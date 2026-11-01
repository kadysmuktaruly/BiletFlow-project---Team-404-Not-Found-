# BiletFlow: plan for Reports 3 and 4 (with Report 2 backfill as step 0)

> After approval, this file is committed as `docs/plan-reports-3-4.md` in the first PR.

## Context

Reports 3 and 4 deliver the core ticketing flow (SRS §13.4): free and paid checkout, QR tickets
by email, PDF tickets, promo campaigns with a Campaign QR, and door check-in on the scanner.
They assume Report 2 (accounts and draft events) is done. **It isn't.** `origin/main` has only
the data model, the API skeleton (health check, error shape, CORS, config), and Compose with
db, api and Mailpit. Everything Report 2 promised has to be built first, as step 0.

Sources: SRS v0.3 (`~/Downloads/BiletFlow_SRS_Initial_Draft.pdf`, to be committed under
`docs/srs/`), `BiletFlow_Semester_Plan.docx`, README, CLAUDE.md and the model docstrings.

## 1. What exists vs. what's missing

| Area | State on `origin/main` |
|---|---|
| Data model | **Done.** 27 models, `0001_initial_schema.py`, native enums, DB guarantees, `verify_constraints.sql` (run by hand) |
| API app | Health check (`/api/v1/health`), `AppError` and the single error shape, CORS with credentials, `Settings` with JWT/SMTP/TTL fields |
| Compose | db (:5433), api (:8000, runs migrations on start), mailpit (:8025/:1025), all with health checks. **No web service** |
| Tests | `test_foundation.py` (stubbed session). **No DB-backed harness, no `*_test` DB** |
| CI | `.github/workflows/` is **empty**. Nothing runs on PRs |
| Auth, roles, `app/deps.py` | **Missing.** No hashing, tokens or endpoints |
| Organizer profile, draft events | **Missing** |
| Email sending | **Missing.** SMTP settings exist but there is no sender |
| `apps/web`, `apps/scanner`, `packages/api-types` | **Empty directories** |
| `docs/decisions.md` | Referenced by model docstrings but **missing** |
| SRS in repo | **Missing** (found in `~/Downloads`) |

Model references to code that doesn't exist yet (`app/schemas/scan.py`, `require_event_admin`)
get built in this plan.

## 2. Key design decisions

These follow the SRS, the existing model, and the §12 decisions in the prompt. Where I had to
choose, the choice is marked *(assumption)*.

**Schema.** No migration is needed. Every field below already exists. If one turns out to be
needed, it gets a new revision, never an edit to 0001, and `alembic check` must stay green.

**Auth (SRS 4.1).** Argon2 password hashes. A 15-minute JWT access token in the
`Authorization` header. The refresh token is a JWT in an httpOnly cookie for the web; the scanner
sends `X-Client: scanner` and gets it in the response body (the CORS header is already allowed).
Verify and reset links are purpose-scoped JWTs. The reset token carries a fingerprint of the
current password hash, so it is single-use. Register may choose only `attendee` or `organizer`.
Choosing `organizer` also creates the `OrganizerProfile`. Login and forgot-password responses
never reveal whether an email exists. Publishing an event requires a verified email (SRS UC1
precondition). Checkout does not *(assumption)*.

**Permissions (`app/deps.py`).** `current_user`, `require_role(...)`, `require_event_owner`
(the event's `organizer_profile.user_id` must be the caller), and `require_event_staff` (the
owner, or an active `StaffAssignment`). Anything the caller may not see returns 404.

**Inventory (SRS 4.3, 4.6).** In one transaction:
1. `SELECT … FOR UPDATE` on the event row. This serializes checkout per event, which makes the
   capacity check across ticket types correct.
2. Release any expired reservations for this event (lazy sweep).
3. Run `UPDATE ticket_types SET quantity_reserved = quantity_reserved + :n WHERE … AND
   quantity_sold + quantity_reserved + :n <= quantity_total`. Zero rows updated means
   `sold_out`, and `ck_ticket_types_inventory_within_total` is the backstop.

Paid orders become `awaiting_payment` with
`expires_at = now + ORDER_RESERVATION_TTL_SECONDS` (new setting, default 600). A background task
in the app lifespan sweeps expired orders every 30 s using `FOR UPDATE SKIP LOCKED`. On
confirmation, `reserved → sold`. Free orders (total 0) confirm and issue tickets in the same
transaction. Only general admission is in scope. Assigned seating is a bonus (semester plan,
Report 6).

**Admission token (SRS 4.7, "tamper-resistant").**
`BFT1.<base64url(ticket uuid)>.<base64url(HMAC-SHA256(TICKET_SIGNING_SECRET, "BFT1."+id)[:16])>`
is about 50 characters and fits the existing `tickets.admission_token String(64)` (unique). The
new `TICKET_SIGNING_SECRET` setting gets the same dev-default and production-required rule as
`JWT_SECRET`. The scanner checks the signature, then looks up live status. The `Ticket`
docstring currently says the token "encodes nothing". I'll update that comment to match your
requirement that it encode the ticket ID.

**Campaign token (SRS 4.14).** It stays opaque, as the model says: `BFC1.<random>` in
`promotional_campaigns.qr_token`. The QR encodes `${PUBLIC_BASE_URL}/c/BFC1.…`. The scan parser
only accepts payloads that start with `BFT1.`. Anything containing `BFC1.` returns
`invalid / campaign_qr_not_admission`.

**Payments (SRS 4.6, DEMO).** The provider is `simulated`. `is_simulated=true` and `"demo": true`
appear in every payment schema. `POST /orders/{id}/payments` takes an `Idempotency-Key` header
and `{outcome: "succeed" | "fail"}`. The key is stored scoped as `"{user_id}:{key}"` in
`payments.idempotency_key` (unique). Replaying a key returns the original result. Reusing a key
for a different order returns 409 `idempotency_key_reused`.
- **Succeed:** confirm, issue tickets, send email.
- **Fail:** payment `failed`, order `failed`, stock released, payment-failure email.
- **Abandon:** `POST /orders/{id}/abandon`, or letting it time out. The order becomes `cancelled`
  or `expired` and stock is released.

The activation fee uses the same simulation with `purpose=activation_fee`.

**Processing charges.** `PROCESSING_FEE_BPS` (new setting, default 300, a DEMO placeholder) is
stored in `orders.processing_fee_kzt` and **not** added to `total_kzt`. It only lowers the
organizer's estimated payout *(assumption on the rate)*.

**Activation (SRS 3.2, 4.5).** The checklist uses the five booleans on `PaidSalesActivation`:
- paid ticket type exists (derived)
- simulated identity check
- payout account (masked, `is_simulated`)
- fee paid (`ACTIVATION_FEE_KZT` recorded in `activation_fee_kzt` and linked to the payment)
- terms accepted

When all five are true, status becomes `active`. Creating an order with any `price_kzt > 0` line
returns 409 `paid_sales_not_active` unless the activation is active and not suspended.

**Promos (SRS 4.14).**
- The discount is computed on the server only, from eligible lines (`PromoCodeTicketType`; no
  rows means every ticket type). A percentage discount is applied per line. A fixed discount is
  capped at the eligible subtotal.
- At order creation, `UPDATE promo_codes SET redeemed_count = redeemed_count + 1`. If
  `ck_promo_codes_within_limit` rejects it, the code is `exhausted`. The `PromoRedemption` row is
  written on confirmation. Expiry, failure or abandon decrements the count.
- Reason codes: `promo_not_found`, `promo_expired`, `promo_not_started`, `promo_disabled`,
  `promo_exhausted`, `promo_not_applicable`. They go in `error.code`, and clients translate them.

**Check-in (SRS 4.8).** One transaction:
```sql
UPDATE tickets SET status='checked_in' … WHERE id=:id AND event_id=:e AND status='valid' RETURNING
```
plus an insert into `check_in_records`, where `uq_checkin_active_ticket` is the backstop. If no
row comes back, the current status is read and mapped to `already_used`, `cancelled` or
`refunded`. A ticket from another event, or a bad signature, maps to `invalid`. Event owners and
`StaffRole.EVENT_ADMIN` assignees can undo a check-in (sets `reversed_at`, resets the ticket to
`valid`, writes an audit entry). `CHECK_IN_STAFF` assignees can scan but not undo
*(assumption)*.

**Email.** `EMAIL_BACKEND=smtp|memory` (new setting). Tests use an in-memory outbox. Mail is
sent after commit as a background task, and every send writes a `Notification` row. Templates
are in kk, ru and en, picked by `user.locale`. The order confirmation embeds a QR PNG for each
ticket (and from Report 4 also attaches the PDF). Every payment-related email says **DEMO**.

**Audit.** A small `services/audit.py` writes `entity.verb` entries for these events: publish,
unpublish and cancel; ticket price and quantity changes; staff assignment; activation steps;
payment succeeded and failed; check-in and reversal; promo created and disabled.

**Event cancel.** The event becomes `cancelled`. Its valid tickets become `cancelled`, and its
pending orders become `cancelled` with stock released. Automatic refunds are Report 5 (SRS 4.9).

**Visibility.** `public` events are listed. `unlisted` events open by slug. `private` events are
visible only to the owner and staff (404 for everyone else), because the schema has no invite
token.

**PDF (SRS 4.7).** An A4 page made with reportlab. It contains:
- event name
- date and time in the event's time zone
- venue name and address
- ticket type
- attendee name
- seat, when applicable
- `ticket_number` and the QR (same token as the digital copy)
- status at the time of printing

It contains **no price, payment or card data**. The QR is at least 60 mm with error-correction
level M, pure black on white, with a 4-module quiet zone. A bundled DejaVu Sans font renders
Cyrillic and Kazakh text.

**Campaign QR image.** It looks different from a ticket QR: it has a colored frame, a dashed
border, and a printed caption "PROMO · NOT A TICKET" (translated), plus the event title.

**i18n.** The web uses next-intl with `messages/{kk,ru,en}.json`. The scanner uses i18next with
`locales/{kk,ru,en}.json`. No hard-coded user-facing text. API error codes map to message keys.

**Web auth and compose.** The access token is kept in memory, and the page refreshes it with
`credentials: "include"` on load. localhost:3000 and localhost:8000 are the same site, so
`SameSite=Lax` works. Compose builds the web app (`next build` + `next start`, with
`NEXT_PUBLIC_API_BASE_URL` as a build argument) and health-checks it.

**Demo data.** `python -m app.seed` is idempotent. It creates demo organizer, attendee, staff and
platform-admin accounts (platform admin is never self-assignable). It also creates one free event
and one paid, activated event, plus one cancelled and one refunded ticket so the scanner can show
all five states.

## 3. Branches and PRs (stacked)

Each branch starts from the previous one. Each PR targets the previous branch, and its
description lists the success criteria it meets. Review fixes are merged down the stack, with no
rebases and no force-pushes. PRs stay open for you to merge in order. CI triggers on
`pull_request` for any base branch, so stacked PRs run CI too.

### Step 0: Report 2 backfill (blocks everything)

| # | Branch | Contents |
|---|---|---|
| 0.1 | `chore/r2-ci-test-harness` | **CI** (`.github/workflows/ci.yml`). The API job runs a Postgres 16 service, `uv sync`, ruff check, ruff format check, strict mypy, `alembic upgrade head`, `alembic check`, `verify_constraints.sql` (fails on any `FAIL`) and pytest. **Harness:** `tests/conftest.py` derives `<db>_test`, creates it, migrates it, `TRUNCATE … CASCADE` between tests (the row trigger doesn't fire on TRUNCATE), an httpx ASGI client, factories, and the memory mail outbox. Also: `docs/srs/` (PDF + `srs.md`), `docs/decisions.md` (the §12 decisions above), and this plan as `docs/plan-reports-3-4.md`. |
| 0.2 | `feat/r2-auth-roles` | Hashing, tokens, `/auth/*` (register, login, refresh, logout, verify-email, resend, forgot, reset), `GET /me`, `app/deps.py`, email service and templates (verification and reset emails reach Mailpit). Tests: register cannot pick `platform_admin`, no email enumeration, verify and reset single-use, role and ownership dependencies. |
| 0.3 | `feat/r2-organizer-profile-draft-events` | `GET/PUT /organizer/profile`, simulated payout account, draft event create, edit, list and get (server-derived slug, IANA time zone checked with `zoneinfo`). Tests for ownership and 404 isolation. |
| 0.4 | `feat/r2-web-scaffold-api-types` | Root npm workspaces. `packages/api-types` with `scripts/gen-api-types.sh` (dumps `app.openapi()`, runs openapi-typescript) and a CI drift check. `apps/web`: Next.js + Tailwind + next-intl, register, login, verify, forgot and reset pages, organizer profile, draft-event form. CI web job: eslint and `tsc --noEmit`. |
| 0.5 | `feat/r2-scanner-scaffold` | `apps/scanner`: Expo + expo-router, i18n, login (refresh token kept in SecureStore), camera-permission screen. CI scanner job: eslint, `tsc`, jest. |

### Report 3 (stop for your check at the end)

| Area | Branch | Contents, in build order | Key tests |
|---|---|---|---|
| A Sagidolla | `feat/r3-ticket-inventory` | **The concurrency test comes first.** Then ticket-type CRUD (delete only if never sold, otherwise hide), `POST /orders` with reservation, lazy plus background expiry, free-order issuing, ticket number and BFT1 token, `GET /me/tickets`, `GET /me/tickets/{id}/qr.svg` | `test_last_ticket_sold_once_under_concurrency` (N parallel requests, exactly 1 succeeds), `test_expired_reservation_releases_stock`, `test_free_order_zero_total_issues_tickets`, `test_paid_order_has_no_tickets_until_paid`, `test_admission_token_signature_and_tamper`, per-order limit, sales window, hidden type |
| B Kadys | `feat/r3-payments-activation` | Payment simulation (succeed, fail, abandon), idempotency, activation checklist API and fee payment, paid-checkout gate, order-confirmation email with QR, payment-failure email, DEMO labels | `test_payment_idempotent_retry`, `test_idempotency_key_reuse_conflict`, `test_failed_payment_no_tickets_and_releases`, `test_abandon_releases`, `test_paid_checkout_blocked_until_activation`, `test_confirmation_email_contains_qr` |
| C Alisher | `feat/r3-organizer-event-management` | API: publish, unpublish, cancel, visibility, registration window, capacity, preview, staff assignment (`/organizer/events/{id}/staff`). Web: event management, ticket types, activation checklist, staff screens | publish needs a verified email and at least one ticket type, visibility matrix, registration-window enforcement, capacity across types, cancel cascades, staff assign and revoke |
| E Nurali | `feat/r3-scanner-skeleton` | `GET /checkin/events` (assigned events only). Scanner: event list, camera QR read, **mock** result screens for valid, invalid, cancelled, refunded and already_used (the harness itself shipped in 0.1) | `test_checkin_events_lists_only_assignments`; jest render tests for the 5 screens |
| D Sanzhar | `feat/r3-attendee-purchase-web` | Public `/events` list and detail, ticket selection, attendee details, DEMO payment step (succeed, fail, abandon), confirmation, "My tickets" with QR. **Web service added to Compose.** `app.seed`, `docs/demo-report-3.md` | `tests/e2e/test_report3_flow.py` (free and paid flows over the API, with the outbox checked); web lint and tsc |

**Report 3 checkpoint:** a fresh `docker compose down -v && docker compose up`, then the seed,
then on the web: a free registration and a DEMO paid purchase, with the QR email visible in
Mailpit. The exact steps go in `docs/demo-report-3.md`. I run it myself (curl, plus the Mailpit
API at `:8025/api/v1/messages`), then **stop and post the Report 3 status table.**

### Report 4 (only after you've checked Report 3)

| Area | Branch | Contents | Key tests |
|---|---|---|---|
| G Sagidolla | `feat/r4-promotions-backend` | Campaign and code CRUD, disable, `POST /promo/validate` (preview), promo applied in `POST /orders`, redemption reserve and release, `GET /campaigns/resolve/{token}`, §4.14 reporting (redemptions, orders, tickets sold, gross, discount, net) | `test_promo_limit_holds_under_concurrency`, `test_code_case_insensitive`, a test for each reason code, `test_client_cannot_set_discount`, `test_campaign_token_resolves_event_and_code`, `test_campaign_and_admission_tokens_disjoint` |
| F Kadys | `feat/r4-check-in-api` | `POST /checkin/events/{id}/scan`, manual check-in, undo (with audit), stats, search, staff-only access, campaign rejection. Confirm Compose runs db, api, web and mailpit, all healthy | `test_double_scan_concurrent_one_checkin`, a test for each of the 5 states, `test_campaign_qr_rejected_at_checkin`, `test_unassigned_staff_404`, `test_undo_writes_audit`, `test_checkin_under_2s` (perf_counter, p95 over 50 scans) |
| I Alisher | `feat/r4-pdf-tickets-campaign-screens` | `GET /me/tickets/{id}/pdf`, PDF attached to the confirmation email, `GET /organizer/campaigns/{id}/qr.png`. Web: campaign create, list and disable, Campaign QR download | the PDF text has every §4.7 field and no `₸`, price or payment strings; the QR decodes to the same token; ticket_number matches the digital copy; email attachment present |
| H Sanzhar | `feat/r4-promo-checkout-attendee-list` | Promo field showing the code, discount and new total; the `/c/[token]` route resolves and opens the event with the code applied; organizer attendee list with search and status (`GET /organizer/events/{id}/attendees`) | attendee-list API search and status filter and 404 isolation; web lint and tsc |
| J Nurali | `feat/r4-scanner-live-checkin` | Live results with color and text, manual search, undo, live counts (polling), `docs/scanner-device-test.md` | jest tests for payload classification and result mapping; API duplicate-scan test reused |
| — | `test/r4-core-flow-e2e` | `tests/e2e/test_core_flow.py` and `docs/demo-report-4.md` | publish → campaign → resolve QR → pay with promo → email and PDF → check-in → second scan `already_used` → Campaign QR at the door rejected |

## 4. Known Partials (stated up front, not claimed)

- **Physical device testing (J):** this can't be done here. It's a manual checklist in
  `docs/scanner-device-test.md` covering a grayscale print, a Campaign QR rejection, and mobile
  data. → **Partial** until the team runs it.
- **Grayscale-print scan (I):** this is covered by a decode test on the rendered QR and the
  module-size rules, but a physical print can't be tested here. → **Partial** for that one part.
- **Expo on a device:** CI covers lint, tsc and jest only.
- **Record a demo video** (semester plan): this is for the team to do.
- **"Merged to main" in the semester plan's definition of done:** the PRs stay open per your
  instruction, so the status table reports them as "Done (PR open)".

## 5. Verification

For every PR, from `apps/api`: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run alembic check && uv run pytest`.
Also `verify_constraints.sql` on a fresh DB, and `npm run lint && npm run typecheck` (plus
scanner jest) for the TS apps. Regenerate `packages/api-types` whenever the API changes; CI
fails on drift.

At each checkpoint: run `docker compose down -v && docker compose up --build`, wait for all
services to be healthy, run the seed, follow the demo doc step by step, and check emails through
the Mailpit API. At the end of each report, post the status table (Owner area | Commitment |
Done / Partial / Carried over | PR link | evidence).

## 6. New settings (added to `config.py` and `.env.example`)

`TICKET_SIGNING_SECRET`, `ORDER_RESERVATION_TTL_SECONDS=600`, `PROCESSING_FEE_BPS=300`,
`EMAIL_BACKEND=smtp`, `WEB_PORT=3000`.
