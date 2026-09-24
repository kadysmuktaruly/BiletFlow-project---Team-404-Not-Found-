# BiletFlow

Self-service event ticketing for Kazakhstan. Organizers create events, sell general-admission
or assigned-seat tickets in KZT, run promo campaigns, and check attendees in at the door with a
QR scanner. Attendees buy tickets, receive them by email, and can open support cases.

> **Status:** early development. The backend data model (27 SQLAlchemy models and the initial
> Alembic migration) is in place. The HTTP API, web app, and scanner app come in later tasks.
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
│   └── api/                    # FastAPI backend (Python 3.12, async SQLAlchemy)
│       ├── app/
│       │   ├── config.py       # Settings read from environment / .env
│       │   ├── db.py           # Async engine and session dependency
│       │   ├── enums.py        # Every enum, stored as a native Postgres enum
│       │   └── models/         # user, event, seating, order, campaign, support, audit
│       ├── migrations/         # Alembic (async); 0001_initial_schema.py
│       └── tests/constraints/  # SQL checks for database-enforced guarantees
├── packages/api-types/         # (planned) shared API types
├── docker-compose.yml          # Postgres 16 (api and web services come later)
└── .env.example                # All environment variables, documented
```

Planned but not yet built: `apps/web` (Next.js frontend) and `apps/scanner` (Expo mobile app
for check-in staff).

## Tech stack

- **API:** FastAPI, Pydantic v2, SQLAlchemy 2.0 (async only), asyncpg, Alembic
- **Database:** PostgreSQL 16
- **Tooling:** [uv](https://docs.astral.sh/uv/), Ruff, mypy (strict), pytest

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

### Verifying database constraints

The most important guarantees are enforced by Postgres itself, not by application code.
`tests/constraints/verify_constraints.sql` checks them against a migrated database. The script
writes rows, so use a throwaway database:

```bash
docker compose exec -T db psql -U biletflow -d biletflow -q -f - \
  < apps/api/tests/constraints/verify_constraints.sql 2>&1 | grep -E 'PASS|FAIL'
docker compose down -v     # reset afterwards
```

See [`apps/api/tests/constraints/README.md`](apps/api/tests/constraints/README.md) for what
each check covers.

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
