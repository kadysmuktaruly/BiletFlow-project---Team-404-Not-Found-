# Database constraint checks

`verify_constraints.sql` asserts that the guarantees SRS Section 7 requires are enforced
*by the database*, not by whichever handler happens to remember them. Every `expect_failure`
block must be rejected by Postgres; every `PASS` line means the database refused something
it should refuse.

Run it against a freshly migrated database:

```bash
docker compose up -d db
cd apps/api && uv run alembic upgrade head
docker compose exec -T db psql -U biletflow -d biletflow -q -f - \
  < tests/constraints/verify_constraints.sql 2>&1 | grep -E 'PASS|FAIL'
```

It writes rows, so run it on a scratch database — `docker compose down -v` afterwards.

What it covers, and why each one matters:

| Check | SRS | Guarantee |
|---|---|---|
| seat double-sell blocked | 4.3.1 | `uq_ticket_active_seat` — two orders can never hold one seat |
| double seat hold blocked | 4.3.1 | `uq_seat_hold_active` — one live hold per seat |
| promo over-redemption blocked | 7 | `ck_promo_codes_within_limit` — the counter is safe to increment concurrently |
| audit UPDATE / DELETE blocked | 4.16 | the append-only trigger |
| discount over subtotal blocked | 4.14 | a server-side discount can zero an order, never invert it |
| ticket oversell blocked | 4.3 | sold + reserved can never exceed the total |
| malformed campaign discount blocked | 4.14 | a percentage campaign cannot also carry a fixed KZT amount |
| refunded ticket frees its seat | 4.9 | the partial index releases as well as blocks |

TODO(week-10): port this to pytest so CI runs it on every pull request. It is SQL today
because the ORM layer that would express it does not exist yet.
