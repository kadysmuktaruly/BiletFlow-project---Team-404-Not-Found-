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
├── docker-compose.yml          # db, api, mailpit
└── .env.example                # All environment variables, documented
```

## Tech stack

- **API:** FastAPI, Pydantic v2, SQLAlchemy 2.0 (async only), asyncpg, Alembic
- **Database:** PostgreSQL 16
- **Web:** Next.js 16 (App Router, TypeScript, Tailwind CSS), next-intl, openapi-fetch
- **Scanner:** Expo SDK 58 (React Native, TypeScript), expo-router, expo-camera, i18next
- **Tooling:** [uv](https://docs.astral.sh/uv/), Ruff, mypy (strict), pytest, npm workspaces

## Getting started

Requirements: Docker and [uv](https://docs.astral.sh/uv/).

```bash
# 1. Configure the environment
cp .env.example .env

# 2. Start Postgres (exposed on host port 5433 by default)
docker compose up -d db

# 3. Install dependencies and apply the schema
cd apps/api
uv sync
uv run alembic upgrade head
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

### Continuous integration

`.github/workflows/ci.yml` runs on every pull request, whatever its base branch:

- **API:** ruff check, ruff format --check, strict mypy, `alembic upgrade head`,
  `alembic check`, and pytest against a Postgres 16 service.
- **Web:** eslint, the kk/ru/en key check, `tsc` for every workspace, and a production build.
- **Scanner:** `expo lint`, the kk/ru/en key check, `tsc`, and jest.
- **API types:** regenerates `packages/api-types` and fails if it differs from what's committed.

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
| `POST /auth/verify-email` | Confirm the email with the token from that link. |
| `POST /auth/resend-verification` | Send the link again. |
| `POST /auth/login` | Returns a 15-minute access token. Browsers get the refresh token as an httpOnly `bf_refresh` cookie; clients sending `X-Client: scanner` get it in the body. |
| `POST /auth/refresh`, `POST /auth/logout` | Rotate the session, or clear the cookie. |
| `POST /auth/forgot-password`, `POST /auth/reset-password` | Email a single-use reset link, then set a new password. Resetting signs out every other session. |
| `GET /me`, `PATCH /me` | The signed-in user. Name, phone and language can be changed; role and email cannot. |

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
| `ACTIVATION_FEE_KZT` | `5000` | Paid sales activation fee (placeholder amount) |
| `CURRENCY` | `KZT` | Currency for the initial release |
