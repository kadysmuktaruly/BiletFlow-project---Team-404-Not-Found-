# BiletFlow status against the semester plan

Audit date: **Tue, Nov 17, 2026** (Report 6 window). Feature freeze: **Sun, Nov 29**.
Audited branch: `feat/r3-attendee-purchase-web` @ `5108c3a`, the tip of the open PR stack.
Spec: SRS v0.3 ([`docs/srs/srs.md`](srs/srs.md)), the semester plan and the model docstrings.

## Progress notes (newest first)

- **Nov 17 — Row 3: PDF tickets and Campaign QR.** [#17](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/17): A4 PDF with every
  SRS 4.7 field and no payment data; its QR decodes from 72-dpi grayscale renders; PDF
  attached to confirmation emails (checked in Mailpit). Campaign QR as SVG and A5 poster,
  labelled "PROMO · NOT A TICKET". pytest 197 passed. Next: web screens (`feat/r4-web-promo-campaigns-attendees`).
- **Nov 17 — Row 2: promotions backend.** [#16](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/16): campaigns with one
  case-insensitive code and an opaque `BFC1.` link, server-side % / fixed-KZT discounts,
  six rejection reasons, limit holds under 10 concurrent buyers, per-campaign report.
  pytest 189 passed. Next: PDF tickets and the Campaign QR image (`feat/r4-pdf-campaign-qr`).
- **Nov 17 — Row 1: check-in API.** [#15](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/15): atomic scan (10 concurrent scans →
  one admission), five live results, Campaign QR rejected, staff-only (404), authorized undo
  with audit, counts, manual search, p95 under 2 s. pytest 176 passed. Next: promotions
  backend (`feat/r4-promotions-backend`).
- **Nov 17 — Docker fix.** [#13](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/13): compose runs `next dev` by default, so the
  stack fits a 2 GB Docker VM; `WEB_BUILD_TARGET=runtime` builds the production image for the
  demo. All four services healthy and six web pages return 200. Next: `feat/r4-check-in-api`.
- **Nov 17 — Audit.** This file. Ten Report 2–3 PRs (#3–#12) wait for review; Report 4 onward
  is missing. Work continues stacked on #12 (see "Review order").

## Review order

Merge from the top down. Each PR targets the one above it; after one merges, the next is
retargeted to `main` and rebased. Suggested reviewer = the plan's owner for that area.

| Order | PR | Summary | Suggested reviewer |
|---|---|---|---|
| 1 | [#3](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/3) | CI workflow, DB-backed pytest harness on `*_test`, SRS and plan docs | Nurali (tests) |
| 2 | [#4](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/4) | Sign-up, login, Argon2, refresh cookie, verify and reset emails, role dependencies | Kadys (auth) |
| 3 | [#5](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/5) | Organizer profile, DEMO payout account, draft events with IANA time zones | Sagidolla (backend) |
| 4 | [#6](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/6) | Next.js scaffold with next-intl, auth and organizer pages, generated `api-types` | Sanzhar (web) |
| 5 | [#7](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/7) | Expo scanner scaffold: sign-in, SecureStore, camera permission | Nurali (scanner) |
| 6 | [#8](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/8) | Ticket types, inventory reservation, last-ticket concurrency test, orders, signed QR tokens | Sagidolla (tickets/orders) |
| 7 | [#9](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/9) | DEMO payments with idempotency keys, paid-sales activation checklist, order emails | Kadys (payments infra) |
| 8 | [#10](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/10) | Publish/unpublish/cancel, visibility, capacity, preview, staff; organizer event hub | Alisher (organizer) |
| 9 | [#11](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/11) | `GET /checkin/events`; scanner event list, camera, five result screens | Nurali (scanner) |
| 10 | [#12](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/12) | Attendee purchase flow on the web, web in Compose, demo seed, Report 3 demo script | Sanzhar (web) |
| 11 | [#13](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/13) | Compose web runs `next dev` to fit a 2 GB Docker VM; production target for the demo | Kadys (infra) |
| 12 | [#15](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/15) | Live check-in API: atomic scan, five results, undo, counts, manual search | Kadys (check-in), Nurali (scanner) |
| 13 | [#16](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/16) | Promotions backend: campaigns, server-side discounts, redemption limit, Campaign QR resolve | Sagidolla (promos), Alisher |
| 14 | [#17](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/17) | A4 PDF tickets (emailed too) and Campaign QR SVG/PDF downloads | Alisher (PDF), Sagidolla |

New Phase 1 PRs are added below as they open.

## Decisions log

| Date | Decision | Reason |
|---|---|---|
| Nov 17 | `docs/STATUS.md` lives only on the `docs/status` branch (PR off `main`). Feature PRs don't edit it. | Feature PRs are stacked; editing one file in all of them would conflict at every rebase. |
| Nov 17 | Phase 1 branches stack on #12, each on the previous one; row 1 sits on #13 so the chain stays linear. | Team lead's decision; `main` lacks the Report 2–3 code. One chain is simpler to retarget than a fork. |
| Nov 17 | Check-in: every scan returns 200 with a `result`; `invalid` has a `reason` (`unrecognized`, `wrong_event`, `campaign_qr_not_admission`). Undo is by ticket id; Platform Admins can't scan unless assigned. | A scan result is data, not an error. SRS 4.8 limits the door to assigned events. |
| Nov 17 | The Docker fix (#13) targets #12's branch, not `main`. | `apps/web` and the compose web service don't exist on `main` yet. |
| Nov 17 | Compose's web service defaults to `next dev`; `WEB_BUILD_TARGET=runtime` builds the production image. | `next build` was OOM-killed at 2 GB even with a 1536 MB heap cap (Turbopack's native memory isn't capped by it). `next dev` fits. |
| Nov 17 | Raised the auditing laptop's Docker VM from 2 GB to 6 GB. The runtime is **Colima**, not Docker Desktop. Backup: `~/.colima/default/colima.yaml.bak-2026-11-17`. All 19 containers that were running before the restart are running again (3 from other projects needed a manual `docker start`). | `next dev` was also killed at 2 GB because other projects' containers use about 900 MB of the VM. 6 GB is under half of the laptop's 16 GB. |
| Nov 17 | No `Co-Authored-By` or "Generated with Claude Code" lines in commits or PRs. | CLAUDE.md forbids them. |
| Nov 17 | Reviewers are named in each PR description instead of being requested on GitHub. | The teammates aren't collaborators on the repository, so GitHub can't request their review. |
| Nov 17 | Promotions: one code per campaign; codes unique platform-wide; % rounds down per line, fixed amount capped and split proportionally; discount and eligible types immutable after creation; campaigns active on creation. Full list in `docs/decisions.md`. | Simplest model that meets SRS 4.14 and keeps past orders explainable. |
| Nov 17 | PDF: no order reference on the print; cancelled/refunded tickets still download with a large "not valid" status; DejaVu Sans vendored for Cyrillic; mypy treats reportlab as untyped instead of adding `types-reportlab`. | SRS 4.7 "no unnecessary sensitive information"; stub package isn't approved. |

## Blocked

Nothing yet.

## How to read this table

The semester plan defines **Done** as merged to `main`, CI green, at least one automated test,
works in the demo stack, and documented.

**Nothing after the foundation is merged.** `main` has only the data model, the API skeleton
and Compose with db, api and Mailpit (PRs #1 and #2). Everything from Report 2 and Report 3 is
in a stack of ten open PRs, **#3 → #12**. Each one targets the PR below it, and all of them
have green CI. They have been waiting for review since Nov 1. So the best status any Report 2
or 3 item can have is:

- **Partial (unmerged):** built, tested and documented, and CI is green. The only thing left
  is reviewing and merging its PR.
- **Partial:** some of the work exists and real gaps remain (listed under "Left").
- **Missing:** nothing usable exists beyond the data model.

### Checks run on the audited branch (Nov 17)

| Check | Result |
|---|---|
| `uv run ruff check .` | pass |
| `uv run ruff format --check .` | pass (85 files) |
| `uv run mypy .` (strict) | pass (83 files) |
| `uv run alembic check` | pass, no new operations |
| `uv run pytest` | **161 passed** in 20.8 s |
| web `npm run lint` (eslint + key parity) | pass, 326 keys in kk/ru/en |
| `npm run typecheck --workspaces` | pass |
| scanner `npm run lint` (expo lint + key parity) | pass, 51 keys in kk/ru/en |
| scanner `npm test` (jest) | **19 passed** |
| GitHub CI on PRs #3–#12 | all green (latest runs Nov 1) |
| `docker compose up --build` on the auditing laptop | **web image fails**: `next build` is killed with SIGKILL (out of memory). The Docker VM has 2 GB and the README requires 4 GB. CI's production build passes, so this is the machine, not the code. api, db and Mailpit run and serve the seeded events. |

## Status by commitment

| Report | Owner | Commitment | Status | Evidence | Left |
|---|---|---|---|---|---|
| 2 | Kadys | Sign-up, login, Argon2 hashing. Self-registration chooses only attendee or organizer. Reusable role dependencies (Attendee, Organizer, Event Admin via `StaffAssignment`, Platform Admin) | Partial (unmerged) | PR #4. `app/routers/auth.py`, `app/deps.py`. `tests/test_auth.py` (20 tests, incl. `test_register_cannot_self_assign_privileged_roles`), `tests/test_roles.py` | Merge #3, #4 |
| 2 | Kadys | Organizer reads and updates their profile and contact info | Partial (unmerged) | PR #5. `GET/PUT /organizer/profile`, `tests/test_organizer.py` | Merge #5 |
| 2 | Sanzhar | Web pages: registration, login, organizer profile | Partial (unmerged) | PR #6. `apps/web/src/app/[locale]/(auth)/*`, `organizer/profile` | Merge #6. No browser-level test yet (Playwright arrives in Report 6) |
| 2 | Nurali | Expo login and camera permission request | Partial (unmerged) | PR #7. `apps/scanner/src/app/login.tsx`, `home.tsx` (`useCameraPermissions`), `__tests__/login.test.tsx` | Merge #7. Physical-device run is a manual task (below) |
| 2 | Kadys | Organizer creates a draft event (title, description, category, venue, date, time, IANA time zone) | Partial (unmerged) | PR #5. `POST /organizer/events`, `tests/test_events_draft.py` (8) | Merge #5 |
| 2 | Kadys | Compose runs db, api, Mailpit. CI runs ruff, mypy, pytest, `alembic check`, TS lint and typecheck. `packages/api-types` generated from OpenAPI | Partial (unmerged) | Compose on `main` (#2). CI `.github/workflows/ci.yml` (#3). api-types plus drift check (#6) | Merge #3, #6 |
| 3 | Kadys | Verification and reset emails reach Mailpit, with no account enumeration | Partial (unmerged) | PR #4. `test_*_never_reveals_whether_email_exists`, `test_register_existing_email_looks_identical_and_sends_nothing` | Merge #4 |
| 3 | Kadys | DEMO payment simulation (succeed, fail, abandon) with idempotency keys. Paid checkout blocked until the activation checklist is complete | Partial (unmerged) | PR #9. `tests/test_payments.py` (14, incl. `test_concurrent_retries_with_one_key_charge_once`), `tests/test_activation.py` (5) | Merge #9 |
| 3 | Sagidolla | Ticket-type CRUD, reservation with expiry, **last-ticket concurrency test**, free tickets issued at once, paid only after payment, unique ID and signed QR token | Partial (unmerged) | PR #8. `test_last_ticket_sold_once_under_concurrency` (written before checkout, commit `37e34eb`), `tests/test_orders.py` (12), `test_ticket_types.py`, `test_tokens.py` | Merge #8 |
| 3 | Alisher | Organizer publish, unpublish, cancel; visibility, registration window, capacity; preview; ticket types; activation checklist screen; assign Event Admins | Partial (unmerged) | PR #10. `tests/test_event_lifecycle.py` (11), `tests/test_staff.py`. Web `organizer/events/[eventId]/*` | Merge #10 |
| 3 | Sanzhar | Attendee web flow: list, detail, selection, attendee details, DEMO payment, confirmation, My tickets with QR. Sign-in required. Strings in one module | Partial (unmerged) | PR #12. `components/attendee/*`, `messages/{kk,ru,en}.json`. API-level `tests/e2e/test_report3_flow.py` | Merge #12. No browser test |
| 3 | Nurali | Scanner lists only assigned events and reads QR with the camera | Partial (unmerged) | PR #11. `GET /checkin/events`, `tests/test_checkin_events.py`, `scan/[eventId].tsx` | Merge #11 |
| 3 | Kadys | pytest + httpx against the `*_test` DB in CI | Partial (unmerged) | PR #3. `tests/conftest.py`, `tests/test_harness.py` | Merge #3 |
| 4 | Kadys | Check-in API: signed token plus live status, five results, atomic, assigned staff only, undo, counts, manual search, Campaign QR rejected, under 2 s | Partial (unmerged) | [#15](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/15). `app/services/checkin.py`, `require_event_staff` in `app/deps.py`, `tests/test_checkin.py` (15 tests incl. `test_double_scan_concurrent_one_checkin`, `test_checkin_under_2s`) | Merge #15 |
| 4 | Sagidolla | Promotions: % or fixed KZT, validity, max redemptions, eligible types, case-insensitive codes, server-side discounts, limit under concurrency, Campaign QR token resolves, clear rejection reasons | Partial (unmerged) | [#16](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/16). `app/services/promotions.py`, `app/routers/campaigns.py`, `tests/test_promotions.py` (13 tests incl. `test_promo_limit_holds_under_concurrency`) | Merge #16 |
| 4 | Sanzhar | Checkout shows code, discount and new total; campaign link pre-applies the code; organizer attendee list with search and status | **Missing** | — | All |
| 4 | Alisher | Server-generated A4 PDF ticket (all fields, no payment data, grayscale-scannable QR, same ticket ID) | Partial (unmerged) | [#17](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/17). `app/tickets/pdf.py`, `GET /me/tickets/{id}/pdf`, emailed; `tests/test_documents.py` decodes the QR at 72/150/300 dpi grayscale | Merge #17. Physical print test (manual) |
| 4 | Alisher | Campaign management screens; downloadable Campaign QR labelled "Promo, not a ticket" | Partial | Downloadable Campaign QR SVG/PDF with the label ([#17](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/17)) | Web campaign screens (row 4) |
| 4 | Nurali | Scanner live check-in: five states with color and text, manual search, undo, live counts | Partial | Five result screens with color, symbol and text (`components/result-view.tsx`, `__tests__/checkin.test.tsx`), but the result is **simulated on the phone** | Wire to the live API, manual search, undo, counts |
| 4 | Kadys | `docker compose up` starts db, api, web, Mailpit | Partial (unmerged) | PR #12 adds the web service with a health check | Merge #12. Team machines need at least 4 GB for Docker |
| 5 | Kadys | Notification interface; email and in-app for every trigger; kk/ru/en templates; in-app list API | Partial | `app/services/notifications.py` records **email** rows only. kk/ru/en emails for verification, reset, order confirmation, payment failure (`app/i18n/emails.py`). All 11 trigger types exist in `NotificationType` | In-app channel, list and mark-read API, templates for event update, cancellation, refund, payout, support |
| 5 | Kadys | Audit entries for every payment, refund, activation, suspension and admin action; append-only test | Partial | `app/services/audit.py`, called by payments, activation, events, staff, ticket types. UPDATE and DELETE blocked in `tests/constraints/verify_constraints.sql`, run by `test_constraints_sql.py` | Refund, suspension and admin audits (those features don't exist yet) |
| 5 | Sagidolla | Refund policy, cancel free registrations, idempotent full refunds, refunded or cancelled tickets fail check-in, event cancel auto-refunds and notifies | **Missing** | `Event.refund_policy`, `Refund` model. Event cancel already cancels tickets (`test_cancel_cancels_tickets_and_releases_unpaid_orders`) but doesn't refund | All refund logic |
| 5 | Sanzhar | Web: attendee order history and detail, organizer order list with confirmed cancel and refund, notification center, event-cancellation screen | Partial | `GET /me/orders`, `/orders/[orderId]` confirmation page, Cancel action in the event hub | Order history list, organizer orders, dialogs, notification center |
| 5 | Alisher | Platform admin portal: search, suspend users and events, suspend paid sales, activation records, set activation fee, reported events, CSV export | **Missing** | `PlatformAdminUser` dependency; seeded admin account; `is_suspended` columns | All. **Needs model changes**: no table for event reports or runtime platform settings |
| 5 | Nurali | Support cases with context, categories, polled thread, assignment, four statuses, organizer-to-platform cases, 404 isolation | **Missing** | Models only (`app/models/support.py`, `is_organizer_case`) | All |
| 6 | Alisher | Analytics API (capacity, sales, revenue, over time, by type, campaigns, attendance; filters; own events only; doesn't slow checkout) | **Missing** | Per-type counts exist on ticket-type responses | All |
| 6 | Alisher | Event duplication (configuration only) | **Missing** | `Event.duplicated_from_event_id` column | All |
| 6 | Sanzhar | Dashboard: line chart over time, bar chart by ticket type, filters | **Missing** | — | All (needs a chart library) |
| 6 | Alisher | Event history: Upcoming / Active / Completed / Cancelled, read-only past events, audit timeline with filters, duplicate button | **Missing** | Audit rows are written (see Report 5) | All |
| 6 | Kadys | Hardening: login and sign-up rate limiting, no secrets in repo, backup-and-restore script, HTTPS proxy proposal | Partial | Production refuses dev secrets (`test_production_requires_real_secrets`), `.env` gitignored | Rate limiting, secret scan, backup/restore script, proxy proposal |
| 6 | Kadys | Seed: organizers, free meetup, paid KZT concert, ticket types, campaigns, orders | Partial (unmerged) | PR #12. `app/seed.py`, `tests/test_seed.py`. Two events, four accounts, cancelled and refunded ticket fixtures | Campaigns, more orders. Merge #12 |
| 6 | Nurali | Tests: concurrency for last ticket, promo limit, double check-in; Playwright e2e of the core flow in CI | Partial | Last ticket (#8), double check-in (#15 `test_double_scan_concurrent_one_checkin`), promo limit (#16 `test_promo_limit_holds_under_concurrency`) | Playwright in CI |
| 6 | Sanzhar | Attendee pages in kk and ru (en extra); WCAG 2.1 AA on event pages | Partial | All 326 web keys exist in kk, ru and en and are actually translated (5 keys are identical across locales, e.g. brand names) | Strings for every new screen; keyboard, contrast and label audit |
| Bonus | — | Calendar export, assigned seating | Not started (by rule) | Seating models exist | Only after an explicit go from the team lead |

## Work in progress by teammates

Every branch on `origin` and every PR (#1–#12) was authored from one GitHub account
(`kadysmuktaruly`), the repo's only collaborator. There are **no open PRs or remote branches
from other teammates**, so nothing above is marked "in progress by <name>".

Risk: teammates may have **local, unpushed** work, especially on Report 4 items (promotions,
check-in, PDF, scanner). Ask everyone to push a WIP branch before new work starts on those items.

## Manual tasks for the team

These can't be automated from the repo. Each one is a short checklist.

### Physical-device scanner test (Android and iOS)
- [ ] Install the internal build (or Expo Go) on one Android and one iOS phone.
- [ ] Sign in as the seeded Event Admin; confirm only assigned events are listed.
- [ ] Deny camera permission once, then confirm the blocked state and the path to Settings work.
- [ ] Scan a valid ticket from a phone screen → **valid**. Scan it again → **already used**.
- [ ] Scan the seeded cancelled and refunded tickets → **cancelled**, **refunded**.
- [ ] Scan a Campaign QR → **invalid** ("not a ticket").
- [ ] Undo a check-in as Event Admin; confirm check-in staff can't undo.
- [ ] Repeat the valid scan over **mobile data** (Wi-Fi off) and time it (target under 2 s).
- [ ] Record phone models, OS versions and results in `docs/scanner-device-test.md`.

### Printed grayscale ticket
- [ ] Download a PDF ticket, print it on A4 in **grayscale** on an ordinary office printer.
- [ ] Scan the paper copy at arm's length and in dim light → **valid**, then **already used**.
- [ ] Check that the print shows every SRS §4.7 field and **no price or payment data**.
- [ ] Confirm the printed and on-screen copies show the same ticket number.

### Usability sessions with outside users
- [ ] Recruit 3–5 people outside the team (at least one Kazakh-first and one Russian-first speaker).
- [ ] Tasks: register and buy a ticket, open a campaign link, find My tickets, open a support case;
      organizer: create and publish a free event.
- [ ] Note time per task, errors and confusing wording; file issues tagged `usability`.

### Install the scanner on demo phones
- [ ] Build an internal APK (`eas build --profile preview`) or use Expo Go with the demo API URL.
- [ ] Set `EXPO_PUBLIC_API_BASE_URL` to the demo laptop's LAN IP; check the phone can reach it.
- [ ] Sign in once on each phone before the demo; charge the phones and turn off auto-lock.

### Demo video
- [ ] Run `docker compose down -v && docker compose up --build` on a machine with Docker set to at least 4 GB.
- [ ] Follow the latest `docs/demo-report-*.md` script end to end once without recording.
- [ ] Record: organizer creates an event and campaign → attendee buys via the Campaign QR →
      email and PDF → scanner admits, then rejects the second scan and the Campaign QR →
      support case → analytics.
- [ ] Keep it under the course limit; add captions; label payments as DEMO on screen.

### Slides
- [ ] Problem, users, MVP scope (SRS §8), architecture diagram, demo, testing evidence
      (test counts, concurrency tests), what was cut and why (SRS §13.4), team roles.

### Biweekly reports
- [ ] Copy each item's row from this file; link PRs; attach CI screenshots; list blockers.

## Updating this file

Update the row in the same PR that changes an item's status. A row becomes **Done** only when
its PR is merged to `main`.
