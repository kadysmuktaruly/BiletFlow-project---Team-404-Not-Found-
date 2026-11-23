# SRS compliance report

The whole project checked against the SRS v0.3 (`docs/srs/srs.md`; the authoritative copy is
`docs/srs/BiletFlow_SRS_v0.3.pdf`). The task, the checklist and the rules are in
[`srs-requirements-check-task.md`](srs-requirements-check-task.md). Decisions this report
relies on are in [`decisions.md`](decisions.md#srs-compliance-check-decisions-nov-23).

**Progress:** part 1 of 2, the §13.4 core flow (CORE-1) and the §11 success criteria
(SC-1..SC-12), checked on 2026-11-23 against `main` at `edee44d`. The other areas follow in
part 2. Rows not reached by Nov 28 will be marked Deferred.

**Statuses:** Pass / Fixed (PR link) / Partial / Missing / Deferred (reason) / Manual /
Bonus–built / Bonus–not built / Excluded. The same set is used in
[`scanner-requirements-check.md`](scanner-requirements-check.md). **(team)** marks a team
requirement that isn't in the SRS; **(decision)** marks a recorded decision.

## Checks run

All run locally on 2026-11-23 on `main` at `edee44d`.

| Check | Command | Result |
|---|---|---|
| API lint | `uv run ruff check .` | Pass: "All checks passed!" |
| API format | `uv run ruff format --check .` | Pass: "120 files already formatted" |
| API types | `uv run mypy .` (strict) | Pass: "no issues found in 118 source files" |
| API tests | `uv run pytest` | Pass: **259 passed** in 55 s |
| Migrations | `uv run alembic check` | Pass: "No new upgrade operations detected." |
| Web lint + i18n keys | `npm run lint -w @biletflow/web` | Pass: eslint clean, "712 keys in kk, ru, en" |
| Web types | `npm run typecheck -w @biletflow/web` | Pass. The first run failed on a stale generated file (`.next/dev/types/validator.ts` pointed to a deleted `account` route). After removing `.next/dev/types` it passed. CI on `main` passes. |
| Web unit tests | `npm test -w @biletflow/web` | None exist. The web app is covered by Playwright only. |
| Scanner lint + i18n keys | `npm run lint -w @biletflow/scanner` | Pass: "80 keys in kk, ru, en" |
| Scanner types | `npm run typecheck -w @biletflow/scanner` | Pass |
| Scanner tests | `npm test -w @biletflow/scanner -- --ci` | Pass: **70 passed**, 9 suites |
| Playwright | `E2E_BASE_URL=http://localhost:3210 npm run e2e -w @biletflow/web` | Pass: **8 passed** (core flow + 7 smoke) in 3.0 min |
| Docker stack | `docker compose up --build -d --wait` (`WEB_PORT=3210`, because 3000 is taken on this machine) | Pass: db, mailpit, api and web all healthy in 36 s. There is no proxy service yet (see DEL-1 and NFR-4, part 2). |
| Smoke | `curl` against the stack | `/api/v1/health` → `{"status":"ok","database":"ok"}`; web `/en` → 200; `/en/events/almaty-jazz-night-demo` → 200; the seeded event's API status is `published`; `/openapi.json` → 200; Mailpit UI → 200 |
| CI | `gh run list --branch main` | The last 3 runs on `main` passed |

## Core flow (§13.4) and success criteria (§11)

Docs: Yes for every row. The README documents each area (API sections for SRS 4.1–4.16,
"End-to-end test (Playwright)"), and the demo flow is in `docs/demo-report-3.md`.

Paths: API tests are in `apps/api/tests/`, Playwright tests in `apps/web/e2e/`, scanner tests
in `apps/scanner/src/__tests__/`.

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| CORE-1 | One Playwright run covers the full core flow: create event → Campaign QR → promo applied → ticket reserved → simulated checkout → ticket issued → support request → entry verified | §13.4 | Partial | `core-flow.spec.ts` "campaign QR → promo purchase → ticket → door → analytics" passes (11.7 s) | Yes | **Gap: no "create event" step.** The test starts from the seeded "Almaty Jazz Night", which is already published and activated. It does cover everything after that: the organizer creates a campaign in the UI, the attendee opens the `/c/BFC1.…` link, the code is applied, DEMO checkout succeeds, the PDF downloads, a support case is opened from the order, and the door API admits the ticket once, then returns `already_used`, and rejects the Campaign QR. **Fix:** the organizer creates and publishes the event in the UI at the start of the test. |
| SC-1 | An organizer publishes a free event and distributes valid tickets | §11, UC1 | Partial | `test_report3_free_registration_and_demo_paid_purchase` (`tests/e2e/test_report3_flow.py`: API only, created → published → free order confirmed at 0 KZT → valid signed QR → confirmation email); `test_publish_needs_a_visible_ticket_type` (`test_event_lifecycle.py`, publishes with a free type and no activation); `test_free_order_zero_total_issues_tickets` (`test_orders.py`); `test_preview_shows_a_draft_to_its_organizer_only` | Yes | **Gap: no test covers a free-only event end to end.** The Report 3 flow publishes an event that also has a paid type and is activated first, so it doesn't prove that a free-only, never-activated event can be published and handed out. The lifecycle test proves that such an event publishes, but nobody registers for it afterwards. UC1's preview step isn't in either test. **Fix:** one API test for UC1: create → free ticket type → preview → publish (no activation) → attendee registers → valid QR ticket and email. |
| SC-2 | An organizer completes the simulated activation and receives demo orders | §11, UC2 | Pass | `test_full_checklist_enables_paid_checkout` (`test_activation.py`): each step is checked, a failed fee payment leaves sales off, the paid fee activates the event (DEMO, 5,000 KZT, idempotent replay), and then a paid order returns 201; `test_paid_checkout_blocked_until_activation` (`test_payments.py`) | Yes | The order in the activation test isn't paid. Paying a paid order is covered by `test_successful_payment_issues_tickets_and_emails_qr`. |
| SC-3 | An attendee checks out and receives a QR ticket | §11, UC3 | Pass | `test_successful_payment_issues_tickets_and_emails_qr`, `test_paid_order_has_no_tickets_until_paid`, `test_failed_payment_no_tickets_and_releases` (`test_payments.py`, `test_orders.py`); Playwright `core-flow.spec.ts` steps 3–4 | Yes | |
| SC-4 | An attendee downloads and prints a ticket that scans | §11, UC7 | Pass | `test_pdf_qr_scans_from_a_grayscale_print_and_matches_the_digital_ticket` (`test_documents.py`, pypdfium2 + zxing on a grayscale render); `test_email_qr_then_printed_pdf_qr_is_already_used` (`test_scanner_srs.py`); Playwright PDF download in `core-flow.spec.ts` | Yes | Printing on real paper is in the manual checklist. |
| SC-5 | An Event Admin validates tickets and duplicate entry is prevented | §11, UC4 | Pass | `test_valid_scan_checks_in_once_then_already_used`, `test_double_scan_concurrent_one_checkin`, `test_manual_and_scan_racing_admit_once`, `test_undo_by_event_admin_and_owner_writes_audit_and_allows_rescan` (`test_checkin.py`); scanner rows 4–8 in [`scanner-requirements-check.md`](scanner-requirements-check.md); Playwright door step | Yes | Real devices are in the manual checklist. |
| SC-6 | An attendee opens a contextual support case and exchanges messages with organizer staff | §11, UC9 | Pass | `test_case_from_a_ticket_carries_its_order_and_event`, `test_thread_internal_notes_assignment_and_statuses`, `test_only_participants_see_a_case` (`test_support.py`); Playwright opens a case from the order page | Yes | The thread test has staff assign the case, reply, and set "waiting for customer". The requester sees the reply but not the internal note. |
| SC-7 | An attendee scans a Campaign QR, gets the discount, and the order is attributed to the campaign | §11, UC10 | Pass | Playwright `core-flow.spec.ts` steps 1–3 and 6 (link → code applied → discount shown → paid; analytics shows 1 redemption); `test_campaign_token_resolves_event_and_code`, `test_percentage_discount_applied_server_side_and_recorded` (`test_promotions.py`) | Yes | |
| SC-8 | The scanner rejects Campaign QRs and still accepts valid tickets | §11, §4.14 | Pass | `test_real_campaign_qr_is_rejected_and_the_next_ticket_still_works` (`test_scanner_srs.py`); `test_campaign_qr_is_never_admission` (`test_checkin.py`); scanner row 10; Playwright door step (`campaign_qr_not_admission`) | Yes | |
| SC-9 | Organizers see accurate ticket, attendance, payment and refund records | §11 | Pass | `test_figures_for_one_event` (`test_analytics.py`, exact figures for sold, refunded, gross, discounts, refunds, fees, payout, checked in and absent); `test_organizer_attendee_list_search_status_and_isolation` (`test_checkin.py`); `test_order_list_search_status_and_actions` (`test_refunds.py`) | Yes | |
| SC-10 | Organizers see sales, capacity, campaign and attendance analytics with no extra checkout fields | §11, UC11 | Pass | `test_figures_for_one_event`, `test_ticket_type_and_date_filters`, `test_only_your_own_events` (`test_analytics.py`); `OrderCreate` / `AttendeeInput` in `app/schemas/order.py` take only ticket ids, quantities, a promo code and name / email / phone | Yes | The analytics test builds its data with ordinary orders only. |
| SC-11 | Organizers review past and cancelled events and the timeline, and duplicate events without copying transactions | §11, UC12 | Pass | `test_events_are_grouped_by_phase`, `test_past_events_are_read_only_but_keep_their_records`, `test_timeline_shows_the_events_story`, `test_duplicate_copies_configuration_but_no_transactions` (`test_history.py`) | Yes | The duplicate test checks that no Order, Ticket, PromotionalCampaign or PaidSalesActivation rows are copied. |
| SC-12 | An admin suspends a suspicious event and further sales stop | §11, §4.12 | Pass | `test_suspending_an_event_stops_sales_at_once`, `test_suspending_paid_sales_stops_paid_checkout_only` (`test_admin.py`) | Yes | The next order gets `409 sales_suspended`, the event leaves the listing, and the action is audited with its reason. |

**Part 1 totals:** 13 rows. 11 Pass, 2 Partial (CORE-1, SC-1), 0 Missing.

## Fix plan for part 1

| Row | Branch | Fix |
|---|---|---|
| CORE-1 | `fix/srs-core-flow` | The Playwright core flow starts by having the organizer create an event, add a ticket type and publish it in the UI, then runs the existing steps on that event. |
| SC-1 | `fix/srs-core-flow` | An API test for UC1: create a draft → add a free ticket type → preview → publish → an attendee registers for free → valid QR tickets and a confirmation email. |
