# SRS compliance report

The whole project checked against the SRS v0.3 (`docs/srs/srs.md`; the authoritative copy is
`docs/srs/BiletFlow_SRS_v0.3.pdf`). The task, the checklist and the rules are in
[`srs-requirements-check-task.md`](srs-requirements-check-task.md). Decisions this report
relies on are in [`decisions.md`](decisions.md#srs-compliance-check-decisions-nov-23).

**Progress:** both parts checked on 2026-11-23 against `main` at `edee44d`. Part 1 is the §13.4
core flow (CORE-1) and the §11 success criteria (SC-1..SC-12). Part 2 is every other row. Fix
PRs are linked in the Status column as they land.

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
| Docker stack | `docker compose up --build -d --wait` (`WEB_PORT=3210`, because 3000 is taken on this machine) | Pass: db, mailpit, api and web all healthy in 36 s. There is no proxy service yet (see DEL-1 and NFR-4). |
| Backup and restore (NFR-9) | `scripts/backup-db.sh <file>`, then `scripts/restore-db.sh <file> biletflow_restore_check` | Pass: a 200 KB dump restored into a scratch database. Row counts match the main database (users 36, events 26, orders 77, tickets 51, audit entries 287). The scratch database was then dropped. |
| Secret scan of the git history (NFR-10) | `docker run --rm -v "$PWD:/repo:ro" zricethezav/gitleaks:v8.21.2 git /repo --redact` | 154 commits scanned, 1 finding, a **false positive**: `generic-api-key` on `apps/api/tests/test_refunds.py:188` in `880d4a0`, which is the idempotency key `"refund-attempt-0001"` in a test. No real secrets. Nothing was added to the repo. |
| Smoke | `curl` against the stack | `/api/v1/health` → `{"status":"ok","database":"ok"}`; web `/en` → 200; `/en/events/almaty-jazz-night-demo` → 200; the seeded event's API status is `published`; `/openapi.json` → 200; Mailpit UI → 200 |
| CI | `gh run list --branch main` | The last 3 runs on `main` passed |

## Core flow (§13.4) and success criteria (§11)

Docs: Yes for every row. The README documents each area (API sections for SRS 4.1–4.16,
"End-to-end test (Playwright)"), and the demo flow is in `docs/demo-report-3.md`.

Paths: API tests are in `apps/api/tests/`, Playwright tests in `apps/web/e2e/`, scanner tests
in `apps/scanner/src/__tests__/`.

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| CORE-1 | One Playwright run covers the full core flow: create event → Campaign QR → promo applied → ticket reserved → simulated checkout → ticket issued → support request → entry verified | §13.4 | Fixed ([#35](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/35), open) | `core-flow.spec.ts` "campaign QR → promo purchase → ticket → door → analytics" passes (11.7 s) | Yes | **Gap: no "create event" step.** The test starts from the seeded "Almaty Jazz Night", which is already published and activated. It does cover everything after that: the organizer creates a campaign in the UI, the attendee opens the `/c/BFC1.…` link, the code is applied, DEMO checkout succeeds, the PDF downloads, a support case is opened from the order, and the door API admits the ticket once, then returns `already_used`, and rejects the Campaign QR. **Fix:** the organizer creates and publishes the event in the UI at the start of the test. |
| SC-1 | An organizer publishes a free event and distributes valid tickets | §11, UC1 | Fixed ([#35](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/35), open) | **New:** `test_uc1_free_event_is_published_and_hands_out_valid_tickets` (`tests/e2e/test_uc1_free_event_flow.py`). Before: `test_report3_free_registration_and_demo_paid_purchase` (`tests/e2e/test_report3_flow.py`: API only, created → published → free order confirmed at 0 KZT → valid signed QR → confirmation email); `test_publish_needs_a_visible_ticket_type` (`test_event_lifecycle.py`, publishes with a free type and no activation); `test_free_order_zero_total_issues_tickets` (`test_orders.py`); `test_preview_shows_a_draft_to_its_organizer_only` | Yes | **Gap: no test covers a free-only event end to end.** The Report 3 flow publishes an event that also has a paid type and is activated first, so it doesn't prove that a free-only, never-activated event can be published and handed out. The lifecycle test proves that such an event publishes, but nobody registers for it afterwards. UC1's preview step isn't in either test. **Fix:** one API test for UC1: create → free ticket type → preview → publish (no activation) → attendee registers → valid QR ticket and email. |
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

**Part 1 totals:** 13 rows. 11 Pass, 2 Fixed ([#35](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/35): CORE-1, SC-1). Both were Partial when first checked.

## Fix plan for part 1

| Row | Branch | Fix |
|---|---|---|
| CORE-1 | `fix/srs-core-flow` | The Playwright core flow starts by having the organizer create an event, add a ticket type and publish it in the UI, then runs the existing steps on that event. |
| SC-1 | `fix/srs-core-flow` | An API test for UC1: create a draft → add a free ticket type → preview → publish → an attendee registers for free → valid QR tickets and a confirmation email. |

---

# Part 2: every other area

Test files are in `apps/api/tests/` unless a path says otherwise. "Docs" means the README's
API section for that SRS area (or a named doc in `docs/`).

## Roles and structure (§1.3, §2.1, §2.3)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| ROLE-1 | Four roles; Event Admin comes from StaffAssignment per event, separate from Platform Admin | §1.3, §2.3 | Pass | `test_role_dependencies` (`test_roles.py`); `test_checkin_events_lists_only_assignments` (`test_checkin_events.py`); `test_only_owner_and_assigned_staff_can_use_the_door` (`test_checkin.py`: platform admins get 404 at the door) | Yes | `UserRole` has attendee / organizer / platform_admin. Event admins are `StaffAssignment` rows. |
| ROLE-2 | Self-registration only as attendee or organizer | §2.3 | Pass | `test_register_cannot_self_assign_privileged_roles`, `test_me_update_cannot_change_role_or_email` (`test_auth.py`) | Yes | |
| ROLE-3 | Web app, iOS/Android scanner app, admin web portal, backend | §2.1 | Pass | `apps/web`, `apps/scanner`, `apps/web/src/app/[locale]/admin`, `apps/api`; Playwright "smoke: admin routes" | Yes | |
| ROLE-4 | Attendees browse, register, buy, download tickets, review orders | §2.3 | Pass | `test_report3_free_registration_and_demo_paid_purchase` (`tests/e2e/`); `test_orders_and_tickets_are_private_to_the_buyer`; Playwright "smoke: attendee routes" | Yes | |
| ROLE-5 | Organizers create events, configure ticket types, activate paid sales, manage attendees, view sales, assign staff | §2.3 | Pass | `test_events_draft.py`, `test_ticket_types.py`, `test_activation.py`, `test_organizer_attendee_list_search_status_and_isolation`, `test_analytics.py`, `test_assign_list_and_revoke_staff` (`test_staff.py`) | Yes | |
| ROLE-6 | Platform Admins moderate events, manage users, review activations, handle disputes, view reports | §2.3 | Partial | `test_admin.py` (8 tests) | Yes | Disputes: see ADM-5. |

## Free and paid model (§3)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| BIZ-1 | Free events, free tickets, QR tickets, attendee lists, check-in and confirmations cost nothing | §3.1 | Pass | `test_uc1_free_event_is_published_and_hands_out_valid_tickets` ([#35](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/35)); `test_free_order_zero_total_issues_tickets`; `test_free_registration_emails_qr_ticket` | Yes | No fee is charged anywhere on the free path. |
| BIZ-2 | Paid sales stay off until paid ticket type + identity + fee + payout account + terms | §3.2 | Pass | `test_full_checklist_enables_paid_checkout`, `test_activation_needs_a_paid_ticket_type`, `test_confirm_steps_require_true` (`test_activation.py`) | Yes | |
| BIZ-3 | Activation applies per event | §3.2 | Pass | `test_activation_is_per_event_and_owner_only` | Yes | |
| BIZ-4 | Simulation only, labelled DEMO, no real money | §3.2 | Pass | `payment["demo"] is True and payment["is_simulated"] is True` (`test_payments.py`); "DEMO payment" in the email; Playwright checks the DEMO marker on checkout | Yes | |
| BIZ-5 | One-time per-event KZT activation fee from `ACTIVATION_FEE_KZT` or platform settings | §3.3 | Pass | `test_checklist_starts_empty_with_fee_from_settings`; `test_activation_fee_is_a_runtime_setting` (`test_admin.py`) | Yes | Default 5,000 KZT, non-refundable (`decisions.md`). |
| BIZ-6 | *(decision)* Processing charges come out of the organizer's payout; no per-ticket service fee | §3.3, §12 | Pass | `test_processing_fee_recorded_for_organizer_not_charged_to_attendee` (`test_payments.py`); `"processing_fee_kzt" not in body` (`test_orders.py`) | Yes | Recorded in `decisions.md`. |

## Accounts (§4.1)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| ACC-1 | Register with email | §4.1 | Pass | `test_register_creates_unverified_attendee_and_sends_verification`, `test_register_as_organizer_creates_profile` | Yes | |
| ACC-2 | Email verification (Mailpit in dev) | §4.1 | Pass | `test_verify_email_with_emailed_token`, `test_unconfirmed_user_cannot_sign_in`; Playwright "login: an unconfirmed account can't sign in" | Yes | |
| ACC-3 | Sign in, sign out, reset; no response reveals registration | §4.1 | Pass | `test_login_errors_do_not_reveal_whether_email_exists`, `test_register_existing_email_looks_identical_and_sends_nothing`, `test_forgot_password_never_reveals_whether_email_exists`, `test_resend_verification_never_reveals_whether_email_exists`, `test_logout_clears_cookie`, `test_reset_password_is_single_use_and_ends_other_sessions` | Yes | |
| ACC-4 | Organizer profile with contact and payout info | §4.1 | Pass | `test_organizer_reads_and_updates_profile`, `test_payout_account_is_simulated_and_stores_last4_only` (`test_organizer.py`) | Yes | |
| ACC-5 | Server-side role permissions through reusable dependencies | §4.1 | Pass | `test_role_dependencies`, `test_role_dependency_requires_sign_in`, `test_suspended_user_token_is_rejected` (`test_roles.py`); `app/deps.py` | Yes | |
| ACC-6 | Secure password hashing | §7 | Pass | `test_register_creates_unverified_attendee_and_sends_verification` asserts `hashed_password.startswith("$argon2")`; `app/security.py` (argon2) | Yes | |

## Events (§4.2)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| EVT-1 | Create, edit, duplicate, publish, unpublish, cancel | §4.2 | Pass | `test_edit_draft` (`test_events_draft.py`); `test_publish_needs_a_visible_ticket_type`, `test_unpublish_hides_page_and_stops_sales_but_keeps_tickets`, `test_cancel_cancels_tickets_and_releases_unpaid_orders`, `test_invalid_transitions` (`test_event_lifecycle.py`); `test_duplicate_copies_configuration_but_no_transactions` | Yes | |
| EVT-2 | Title, description, category, **images**, venue, date, time; IANA timezone *(team)* | §4.2 | Partial | `test_create_draft_reads_naive_times_in_event_timezone`, `test_create_draft_validation` (`test_events_draft.py`) | Yes | **Gap: one image, by URL only.** `Event.cover_image_url` holds a single URL. The SRS says "images" (plural), and §9 suggests S3-compatible storage. Uploads or several images need a model change and file storage, so this needs your decision (see the open-decision list at the end). The IANA timezone *(team)* passes. |
| EVT-3 | Physical, venue-based events only | §4.2 | Pass | `test_create_draft_validation` (a venue is required); `EventCreate.venue` is required in `app/schemas/event.py` | Yes | There is no online-event type. |
| EVT-4 | Public / unlisted / private behave correctly in listings and direct links | §4.2 | Pass | `test_public_listing_and_visibility`, `test_settings_visibility_window_capacity` (`test_event_lifecycle.py`); `test_private_event_campaign_links_stay_private` | Yes | Private = organizer and staff only (`decisions.md`). |
| EVT-5 | Registration open/close times are enforced | §4.2 | Pass | `test_registration_window_is_enforced_at_checkout`, `test_event_must_be_open_for_registration` | Yes | |
| EVT-6 | Event capacity is enforced | §4.2 | Pass | `test_capacity_holds_across_ticket_types_under_concurrency` (`test_inventory_concurrency.py`); `test_capacity_cannot_drop_below_sold` | Yes | |
| EVT-7 | Preview before publication | §4.2 | Pass | `test_preview_shows_a_draft_to_its_organizer_only`; UC1 test ([#35](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/35)) | Yes | |

## Tickets (§4.3)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| TKT-1 | Free and paid ticket types | §4.3 | Pass | `test_create_free_and_paid_types_with_counts` (`test_ticket_types.py`) | Yes | |
| TKT-2 | Name, description, integer-KZT price, quantity | §4.3 | Pass | `test_create_free_and_paid_types_with_counts`, `test_create_validation` | Yes | |
| TKT-3 | Sales start/end enforced | §4.3 | Pass | `test_sales_window` (`test_orders.py`) | Yes | |
| TKT-4 | Per-order limit enforced | §4.3 | Pass | `test_per_order_limit` | Yes | |
| TKT-5 | Hide without deleting | §4.3 | Pass | `test_delete_only_if_never_ordered_otherwise_hide`, `test_hidden_ticket_type_cannot_be_ordered` | Yes | |
| TKT-6 | Available, reserved, sold, refunded, checked-in counts per type | §4.3 | Pass | `test_create_free_and_paid_types_with_counts` asserts `quantity_available`, `quantity_reserved`, `quantity_refunded`, `quantity_checked_in` | Yes | |
| TKT-7 | Sales stop when inventory runs out; the last ticket can't sell twice | §4.3 | Pass | `test_last_ticket_sold_once_under_concurrency` (`test_inventory_concurrency.py`) | Yes | |

## Assigned seating (§4.3.1, §7) *(bonus)*

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| SEAT-1 | GA or assigned seating per event | §4.3.1 | Bonus–not built | | Yes | The `Venue`, `VenueSection`, `Row`, `Seat` and `SeatHold` models and the `uq_ticket_active_seat` index exist (§6). There's no API or UI. |
| SEAT-2 | One predefined layout | §4.3.1 | Bonus–not built | | Yes | |
| SEAT-3 | Accessible interactive SVG seat map | §4.3.1, §7 | Bonus–not built | | Yes | |
| SEAT-4 | Expiring holds; queries check `expires_at` | §4.3.1 | Bonus–not built | | Yes | `SeatHold.expires_at` exists in the model only. |
| SEAT-5 | No double-sold seat; seat stored on ticket and order item | §4.3.1, §7 | Bonus–not built | | Yes | The columns and the unique index exist. There's no checkout path that uses them. |
| SEAT-6 | Organizer selects and configures the predefined layout | §4.3.1 | Bonus–not built | | Yes | |
| SEAT-7 | Attendee picks seats and sees the price before checkout | §4.3.1 | Bonus–not built | | Yes | |

## Free registration (§4.4)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| FREE-1 | Reserve a free ticket with no payment info | §4.4 | Pass | `test_free_order_zero_total_issues_tickets` (`payment_required` is false) | Yes | |
| FREE-2 | Zero order total | §4.4 | Pass | same test (`total_kzt == 0`) | Yes | |
| FREE-3 | Confirmation email with the QR ticket | §4.4 | Pass | `test_free_registration_emails_qr_ticket` (`test_payments.py`) | Yes | |
| FREE-4 | The registration shows in the organizer's attendee list | §4.4 | Pass | `test_organizer_attendee_list_search_status_and_isolation`; UC1 test ([#35](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/35)) | Yes | |

## Paid sales activation (§4.5)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| ACT-1 | Paid tickets can't be bought before activation (server-side) | §4.5 | Pass | `test_paid_checkout_blocked_until_activation` (`test_payments.py`); `paid_sales_not_active` in `test_full_checklist_enables_paid_checkout` | Yes | |
| ACT-2 | Activation checklist | §4.5 | Pass | `test_checklist_starts_empty_with_fee_from_settings`; Playwright core flow ticks every step in the UI ([#35](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/35)) | Yes | |
| ACT-3 | The fee payment is recorded | §4.5 | Pass | `test_full_checklist_enables_paid_checkout` (`activation_payment`, 2 payment rows for 1 failed + 1 paid attempt) | Yes | |
| ACT-4 | Simulated payout requirements are checked | §4.5 | Pass | same test (`payout_account_required` until the account exists) | Yes | |
| ACT-5 | Activation applies only to the selected event | §4.5 | Pass | `test_activation_is_per_event_and_owner_only` | Yes | |
| ACT-6 | An admin suspends paid sales and checkout stops at once | §4.5 | Pass | `test_suspending_paid_sales_stops_paid_checkout_only` (`test_admin.py`); `test_suspension_after_reserving_blocks_payment` (`test_payments.py`) | Yes | |

## Checkout and payments (§4.6)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| PAY-1 | Select tickets and give attendee details | §4.6 | Pass | `test_free_order_zero_total_issues_tickets` (attendee names), `test_attendee_count_must_match` | Yes | |
| PAY-2 | Inventory reserved during checkout, released on expiry | §4.6 | Pass | `test_expired_reservation_releases_stock`, `test_background_sweep_expires_orders` | Yes | |
| PAY-3 | Totals and processing charges computed on the server | §4.6 | Pass | `test_client_cannot_set_prices_or_totals`; `test_processing_fee_recorded_for_organizer_not_charged_to_attendee` | Yes | |
| PAY-4 | Success / failure / abandonment, DEMO, idempotent | §4.6 | Pass | `test_successful_payment_issues_tickets_and_emails_qr`, `test_failed_payment_no_tickets_and_releases`, `test_abandon_releases`, `test_payment_idempotent_retry`, `test_concurrent_retries_with_one_key_charge_once`, `test_idempotency_key_reuse_conflict` | Yes | |
| PAY-5 | Tickets only after confirmed payment | §4.6 | Pass | `test_paid_order_has_no_tickets_until_paid` | Yes | |
| PAY-6 | Failed or abandoned payments never create valid tickets | §4.6 | Pass | `test_failed_payment_no_tickets_and_releases`, `test_abandon_releases`, `test_expired_order_cannot_be_paid` | Yes | |
| PAY-7 | Organizer sees gross, fees, refunds, estimated payout | §4.6 | Pass | `test_figures_for_one_event` (`gross_kzt`, `processing_fees_kzt`, `refunds_kzt`, `estimated_payout_kzt`) | Yes | |
| PAY-8 | Demo records never presented as real | §4.6 | Pass | `demo` / `is_simulated` flags in `test_payments.py`, `test_refunds.py`; the analytics `"demo": True`; the CSV export marks payments DEMO (`test_csv_export_is_safe_and_audited`) | Yes | |
| PAY-9 | Card data is never stored | §7 | Fixed ([#38](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/38), open) | `Payment` in `app/models/order.py` has only `card_brand` / `card_last4` (no PAN or CVV, by design, see its docstring); the payment request takes only `outcome` | Yes | **Fixed by** `test_card_data_sent_with_a_payment_is_never_stored`: card fields sent by a client are dropped, never stored or echoed, and the model has no card-number or CVV column. Before: **Gap: no test.** Nothing checks that card data sent with a payment is refused and never stored. **Fix:** a test that posts card-looking fields and asserts a 422 and no stored card data. |

## Digital and printable tickets (§4.7, §7)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| DT-1 | Unique ID, event / type / attendee info, signed QR, status | §4.7 | Pass | `test_admission_token_signature_and_tamper`, `test_tokens_signed_with_another_secret_are_rejected` (`test_tokens.py`); `test_free_order_zero_total_issues_tickets` (unique numbers, valid status) | Yes | |
| DT-2 | By email and in the account | §4.7 | Pass | `test_report3_free_registration_and_demo_paid_purchase` (`/me/tickets` and the emails) | Yes | |
| DT-3 | Print-optimized A4 PDF | §4.7 | Pass | `test_pdf_ticket_has_every_field_and_no_payment_data` (`test_documents.py`); Playwright downloads `ticket-BFT-….pdf` | Yes | |
| DT-4 | PDF contents | §4.7 | Pass | `test_pdf_ticket_has_every_field_and_no_payment_data`, `test_pdf_shows_seat_and_live_status`, `test_pdf_in_kazakh_and_russian` | Yes | |
| DT-5 | No payment data on the PDF | §4.7 | Pass | `test_pdf_ticket_has_every_field_and_no_payment_data` | Yes | |
| DT-6 | Scans from a grayscale print (rendered and decoded) | §4.7, §7 | Pass | `test_pdf_qr_scans_from_a_grayscale_print_and_matches_the_digital_ticket` (pypdfium2 + zxing) | Yes | Real paper is in the manual checklist. |
| DT-7 | Digital and print share one ID and admit once | §4.7 | Pass | `test_email_qr_then_printed_pdf_qr_is_already_used` (`test_scanner_srs.py`) | Yes | |

## Scanner app (§4.8, §7, §10)

These rows reuse [`scanner-requirements-check.md`](scanner-requirements-check.md) (the "#" there).

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| MOB-1 | Secure sign-in; only assigned events | §4.8 | Pass | scanner #1, #2 | Yes | |
| MOB-2 | Camera scanning | §4.8 | Fixed ([#33](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/33)) | scanner #3 | Yes | Real camera decoding: Manual (M1–M5). |
| MOB-3 | Server validates authenticity and status in real time | §4.8 | Pass | scanner #4 | Yes | |
| MOB-4 | Five results with color and text | §4.8 | Pass | scanner #5 | Yes | |
| MOB-5 | Atomic check-in, no double entry | §4.8 | Pass | scanner #6 | Yes | |
| MOB-6 | Manual attendee search | §4.8 | Pass | scanner #7 | Yes | |
| MOB-7 | Authorized undo | §4.8 | Fixed ([#33](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/33)) | scanner #8 | Yes | |
| MOB-8 | Registered and checked-in totals | §4.8 | Pass | scanner #9 | Yes | |
| MOB-9 | Online sync; offline *(bonus)* | §4.8, §10 | Pass | scanner #13, #14 | Yes | Offline: Bonus–not built (no offline queue, by design). |
| MOB-10 | Validation under 2 s | §7 | Fixed ([#33](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/33)) | scanner #12 (`test_checkin_under_2s`, `test_checkin_under_2s_on_seeded_demo_data`) | Yes | On a real phone: Manual (M7). |
| MOB-11 | Current iOS and Android | §7 | Manual | scanner manual test M1–M12 | Yes | Needs real devices. |

## Orders, cancellations, refunds (§4.9)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| ORD-1 | Attendees view their orders | §4.9 | Pass | `test_orders_and_tickets_are_private_to_the_buyer`; Playwright "smoke: attendee routes" (`/orders`) | Yes | |
| ORD-2 | Organizer refund policy | §4.9 | Pass | `test_refund_policy_is_set_by_the_organizer_and_shown_publicly` | Yes | |
| ORD-3 | Organizers cancel free registrations | §4.9 | Pass | `test_cancel_free_registration` | Yes | |
| ORD-4 | Full refunds through the simulation, idempotent | §4.9 | Pass | `test_full_refund_invalidates_tickets_returns_stock_audits_and_notifies`, `test_refund_is_idempotent`, `test_concurrent_refund_requests_refund_once`, `test_only_the_event_owner_refunds_or_cancels` | Yes | |
| ORD-5 | Refunded / cancelled tickets fail at check-in | §4.9 | Pass | `test_cancelled_and_refunded_tickets_are_rejected_live`; the refund test scans and gets `refunded` | Yes | |
| ORD-6 | Every payment and refund action is audited | §4.9 | Fixed ([#38](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/38), open) | refunds: `test_full_refund_invalidates_tickets_returns_stock_audits_and_notifies`; activation-fee payments: `activation.*` entries in `test_full_checklist_enables_paid_checkout`; `app/services/payments.py` writes `payment.succeeded` / `payment.failed` | Yes | **Fixed by** `test_ticket_payments_are_audited_whether_they_succeed_or_fail`. Before: **Gap: no test for ticket-payment audit entries.** The code writes them, but no test asserts them. **Fix:** assert both entries in `test_payments.py`. |
| ORD-7 | Cancelling an event cancels tickets, notifies, fully refunds paid orders (team decision) | §4.9 | Pass | `test_cancelling_an_event_refunds_every_paid_order` (`test_refunds.py`); `test_cancellation_notifies_ticket_holders` | Yes | Recorded in `decisions.md`. |

## Notifications (§4.10)

kk/ru/en templates *(team)*: Pass, `test_every_template_exists_in_kk_ru_en_with_the_same_placeholders`
(`test_notifications.py`) and `test_verification_email_uses_the_users_language`.

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| NTF-1 | Account verification | §4.10 | Pass | `test_register_creates_unverified_attendee_and_sends_verification` | Yes | Email. |
| NTF-2 | Registration or purchase confirmation | §4.10 | Pass | `test_registration_is_emailed_and_shown_in_app`, `test_successful_payment_issues_tickets_and_emails_qr` | Yes | Email + in-app. |
| NTF-3 | Payment failure | §4.10 | Pass | `test_payment_failure_is_shown_in_app` | Yes | In-app + email (`order_emails.payment_failed`). |
| NTF-4 | Ticket delivery | §4.10 | Pass | `test_confirmation_email_attaches_a_pdf_per_ticket` (`test_documents.py`) | Yes | |
| NTF-5 | Event updates | §4.10 | Pass | `test_event_changes_notify_each_ticket_holder_once`, `test_drafts_never_notify` | Yes | What counts as an update is in `decisions.md`. |
| NTF-6 | Event cancellation | §4.10 | Pass | `test_cancellation_notifies_ticket_holders` | Yes | |
| NTF-7 | Refund completion | §4.10 | Pass | `test_full_refund_invalidates_tickets_returns_stock_audits_and_notifies` (`refund_completed`) | Yes | |
| NTF-8 | Organizer payout status | §4.10 | Pass | `test_payout_account_status_is_notified` | Yes | |
| NTF-9 | Support: new message, assignment, status change | §4.10 | Pass | `test_thread_internal_notes_assignment_and_statuses` (`support_case_assigned`, `support_status_changed`, `support_new_message`) | Yes | |
| NTF-10 | *(team)* In-app list API and web notification center | §4.13 | Pass | `test_inbox_read_state_and_privacy`; `/notifications` in Playwright "smoke: attendee routes" | Yes | |

## Calendar export (§4.11) *(bonus)*

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| CAL-1 | `.ics` download | §4.11 | Bonus–not built | no `.ics` / `text/calendar` anywhere in `apps/` | n/a | |
| CAL-2 | Google / Outlook links | §4.11 | Bonus–not built | | n/a | |
| CAL-3 | Entry contents | §4.11 | Bonus–not built | | n/a | |
| CAL-4 | Stable UID | §4.11 | Bonus–not built | | n/a | |
| CAL-5 | Cancellation entry | §4.11 | Bonus–not built | | n/a | |
| CAL-6 | No calendar write access | §4.11 | Bonus–not built | | n/a | Trivially true: nothing touches calendars. |

## Administration (§4.12)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| ADM-1 | Search users, events, orders, payments | §4.12 | Pass | `test_search_and_suspend_users`, `test_orders_payments_and_summary`, the search in `test_suspending_an_event_stops_sales_at_once` (`test_admin.py`) | Yes | |
| ADM-2 | Suspend users and events | §4.12 | Pass | `test_search_and_suspend_users`, `test_suspending_an_event_stops_sales_at_once` | Yes | |
| ADM-3 | Review reported events | §4.12 | Pass | `test_reported_events_are_reviewed` | Yes | |
| ADM-4 | Inspect activation records | §4.12 | Pass | `/admin/activations` in `test_only_platform_admins` and `test_suspending_paid_sales_stops_paid_checkout_only` | Yes | |
| ADM-5 | Monitor refunds, disputes, payment failures | §4.12 | Partial | `test_orders_payments_and_summary` (`/admin/payments?status=failed`, `refunds` and `payments_failed` in the summary) | Yes | **Gap: there's no "dispute" concept.** Refunds and failures can be monitored. Disputes don't exist as such, and "advanced dispute workflows" are excluded (§8). Admins can open every support case, so a payment or refund support case could count as a dispute. That needs a decision (see the end of this report). |
| ADM-6 | Configure the activation fee and platform settings | §4.12 | Pass | `test_activation_fee_is_a_runtime_setting` | Yes | |
| ADM-7 | Review escalated support cases and promo-code activity | §4.12 | Fixed ([#40](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/40), open) | support: `list_cases` / `read_case` give Platform Admins every case (`app/services/support.py`); `test_organizer_cases_go_to_the_platform` | Yes | **Fixed by** `GET /admin/promotions` and an admin **Promo codes** tab; `test_promo_code_activity_across_the_platform`. Before: **Gap: admins can't see promo-code activity.** There is no admin endpoint or page for campaigns, codes or redemptions; only organizers see them, for their own events. **Fix:** a read-only `GET /admin/promotions` (code, event, status, redemptions / limit, discount given) with a test, plus an admin tab. |
| ADM-8 | Export operational reports (CSV *(team)*) | §4.12 | Pass | `test_csv_export_is_safe_and_audited` | Yes | Users, events, orders, payments. The test also covers formula injection. |
| ADM-9 | Every admin action is audited | §7 | Pass | `admin.*` audit entries asserted in `test_admin.py` (suspend with reason, export, fee change, report review) | Yes | |

## Support (§4.13, §7)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| SUP-1 | Attendees open a case from an event, order or ticket page | §4.13 | Pass | `test_case_from_a_ticket_carries_its_order_and_event`; Playwright opens one from the order page; "Get help" links in `event-page.tsx`, `order-page.tsx`, `my-tickets-page.tsx` | Yes | |
| SUP-2 | Organizers open platform cases | §4.13 | Pass | `test_organizer_cases_go_to_the_platform` | Yes | |
| SUP-3 | Context attached automatically | §4.13 | Pass | `test_case_from_a_ticket_carries_its_order_and_event`, `test_context_must_be_the_requesters_own` | Yes | |
| SUP-4 | The eight issue categories | §4.13 | Pass | `SupportCategory` in `app/enums.py` (all eight, verbatim) | Yes | |
| SUP-5 | Async thread, polled | §4.13 | Pass | `test_thread_internal_notes_assignment_and_statuses`; the web case page polls every 10 s, the list every 30 s (`components/support/`) | Yes | |
| SUP-6 | Attendee↔organizer staff, organizer↔Platform Admin | §4.13 | Pass | `test_thread_internal_notes_assignment_and_statuses`, `test_organizer_cases_go_to_the_platform` | Yes | |
| SUP-7 | Assign and set the four statuses | §4.13 | Pass | `test_thread_internal_notes_assignment_and_statuses`; `SupportCaseStatus` | Yes | |
| SUP-8 | Notified of replies and status changes | §4.13 | Pass | same test (emails asserted) | Yes | |
| SUP-9 | History retained; access by role and relationship (404) | §4.13, §7 | Pass | `test_only_participants_see_a_case`, `test_private_event_is_not_a_door_in` | Yes | |
| SUP-10 | No attachments *(bonus)* | §8 | Bonus–not built | | Yes | |

## Promo codes and Campaign QR (§4.14, §7)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| PRM-1 | Campaigns per event | §4.14 | Pass | `test_create_campaign_generates_code_and_opaque_campaign_link`, `test_campaign_validation_and_ownership` | Yes | |
| PRM-2 | % or fixed KZT, dates, max redemptions, eligible types | §4.14 | Pass | `test_percentage_discount_applied_server_side_and_recorded`, `test_fixed_discount_is_capped_split_and_limited_to_eligible_types`, `test_update_limits_and_dates_and_disable` | Yes | |
| PRM-3 | Unique code and Campaign QR generated | §4.14 | Pass | `test_create_campaign_generates_code_and_opaque_campaign_link`, `test_codes_are_case_insensitive_and_unique` | Yes | |
| PRM-4 | HTTPS link with an opaque token, no price | §4.14, §7 | Pass | `test_campaign_qr_is_labelled_promo_and_encodes_only_the_link` (`test_documents.py`) | Yes | The link uses `PUBLIC_BASE_URL`, which is plain HTTP in the local stack until Caddy lands (NFR-4). |
| PRM-5 | Scan opens the event with the code pre-applied after server validation | §4.14 | Pass | `test_campaign_token_resolves_event_and_code`; Playwright core flow | Yes | |
| PRM-6 | Code, discount and new total shown before paying | §4.14 | Pass | Playwright core flow ("Code … applied", "Discount (…)" on the event and checkout pages) | Yes | |
| PRM-7 | Clear rejections; case-insensitive | §4.14 | Pass | `test_rejections_give_a_clear_reason`, `test_codes_are_case_insensitive_and_unique` | Yes | |
| PRM-8 | Server-side discounts; atomic limit with a test | §4.14, §7 | Pass | `test_promo_limit_holds_under_concurrency`, `test_database_rejects_redemptions_past_the_limit` | Yes | |
| PRM-9 | Campaign QR visibly different from a ticket QR | §4.14 | Pass | `test_campaign_qr_is_labelled_promo_and_encodes_only_the_link`; Playwright checks the "Promo, not a ticket" label | Yes | |
| PRM-10 | Scanner and admission endpoint always reject Campaign QRs | §4.14, §7 | Pass | `test_campaign_qr_is_never_admission`, `test_real_campaign_qr_is_rejected_and_the_next_ticket_still_works`; scanner #10 | Yes | |
| PRM-11 | Exact per-campaign redemptions, orders, tickets, gross, discount, net | §4.14 | Pass | the campaign rows in `test_figures_for_one_event` (`test_analytics.py`) | Yes | |
| PRM-12 | GA4 *(optional)*, no personal data | §4.14 | Bonus–not built | no GA4 / gtag code in `apps/web` | n/a | Nothing is sent to Google. |

## Analytics (§4.15, §7)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| ANL-1 | Only events you manage | §4.15 | Pass | `test_only_your_own_events` | Yes | |
| ANL-2 | Capacity, sold, remaining, % sold | §4.15 | Pass | `test_figures_for_one_event` | Yes | |
| ANL-3 | Gross, discounts, refunds, net demo revenue | §4.15 | Pass | same | Yes | |
| ANL-4 | Sales over time from order timestamps | §4.15 | Pass | `test_figures_for_one_event` (30 daily points) | Yes | |
| ANL-5 | By ticket type | §4.15 | Pass | `test_ticket_type_and_date_filters` | Yes | |
| ANL-6 | Campaign redemptions, tickets, revenue | §4.15 | Pass | `test_figures_for_one_event` | Yes | |
| ANL-7 | Checked in, absent, check-in % | §4.15 | Pass | `test_figures_for_one_event` (`checked_in` 1, `absent` 2, 33.3%) | Yes | |
| ANL-8 | Event, date range (default 30 days), ticket-type filters | §4.15 | Pass | `test_ticket_type_and_date_filters`; the 30-day default is asserted in `test_figures_for_one_event` | Yes | |
| ANL-9 | Only BiletFlow records; no extra checkout fields | §4.15 | Pass | see SC-10 | Yes | |
| ANL-10 | Analytics don't slow checkout; read-only, no locks | §7 | Pass | `test_analytics_never_holds_up_checkout` (8 dashboards and 8 checkouts at once); `compute()` in `app/services/analytics.py` runs in its own `READ ONLY` transaction with a 5 s `statement_timeout` and no `FOR UPDATE` | Yes | |
| ANL-11 | Seeded numbers match raw records | §4.15 | Pass | `test_figures_for_one_event`: every figure is asserted against a hand-built scenario | Yes | |

## Event history and audit (§4.16, §7)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| HIS-1 | Upcoming / Active / Completed / Cancelled | §4.16 | Pass | `test_events_are_grouped_by_phase` | Yes | |
| HIS-2 | Past events read-only with their records | §4.16 | Pass | `test_past_events_are_read_only_but_keep_their_records` | Yes | |
| HIS-3 | Duplicate without transactions | §4.16 | Pass | `test_duplicate_copies_configuration_but_no_transactions` | Yes | |
| HIS-4 | Chronological timeline per event | §4.16 | Pass | `test_timeline_shows_the_events_story` (newest first) | Yes | |
| HIS-5 | Publish/cancel, price/capacity, refunds, promo, support status, check-ins and reversals | §4.16 | Pass | `test_timeline_shows_the_events_story` (`event.published`, `ticket_type.quantity_changed`, `promo.created`, check-in and reversal); `support_case.status_changed` in `test_support.py`; `promo.disabled` in `test_update_limits_and_dates_and_disable`; `ticket_type.price_changed` in `test_price_and_quantity_changes_are_audited`; refunds in `test_refunds.py` | Yes | The timeline is read from the audit log, so every audited action appears. |
| HIS-6 | Timestamp, actor, action, entity, description | §4.16 | Pass | `test_timeline_shows_the_events_story` | Yes | |
| HIS-7 | Filter by date range and type | §4.16 | Pass | the same test filters by `category=promo` and `date_from` | Yes | |
| HIS-8 | Authorized staff and Platform Admins only | §4.16, §7 | Pass | `test_timeline_shows_the_events_story`: event admin and Platform Admin get 200, check-in staff, strangers and other owners get 404 | Yes | Check-in staff are excluded (`decisions.md`). |
| HIS-9 | Not editable through organizer interfaces; *(decision, beyond the SRS)* append-only in the DB | §4.16 | Pass | `test_audit_entries_cannot_be_edited_or_deleted` (`test_audit.py`: UPDATE and DELETE raise `DBAPIError` from a database trigger); `tests/constraints/verify_constraints.sql` | Yes | |

## Use cases end to end (§5)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| UC-1 | Organizer creates and publishes a free event | UC1 | Fixed ([#35](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/35), open) | `test_uc1_free_event_is_published_and_hands_out_valid_tickets` | Yes | See SC-1. |
| UC-2 | Activate paid sales | UC2 | Pass | `test_full_checklist_enables_paid_checkout`; Playwright core flow ([#35](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/35)) | Yes | |
| UC-3 | Buy a ticket | UC3 | Pass | `test_report3_free_registration_and_demo_paid_purchase`; Playwright core flow | Yes | |
| UC-4 | Check in; a second scan is rejected until undo | UC4 | Pass | `test_undo_by_event_admin_and_owner_writes_audit_and_allows_rescan` | Yes | |
| UC-5 | Refund; ticket invalid; attendee notified | UC5 | Pass | `test_full_refund_invalidates_tickets_returns_stock_audits_and_notifies` | Yes | |
| UC-6 | *(bonus)* Calendar | UC6 | Bonus–not built | | n/a | |
| UC-7 | Print a ticket and it scans | UC7 | Pass | `test_pdf_qr_scans_from_a_grayscale_print_and_matches_the_digital_ticket`, `test_email_qr_then_printed_pdf_qr_is_already_used` | Yes | |
| UC-8 | *(bonus)* Assigned seat | UC8 | Bonus–not built | | n/a | |
| UC-9 | Support request and organizer reply | UC9 | Pass | `test_thread_internal_notes_assignment_and_statuses` | Yes | |
| UC-10 | Buy through a Campaign QR, attributed | UC10 | Pass | Playwright core flow | Yes | |
| UC-11 | Analytics with filters | UC11 | Pass | `test_ticket_type_and_date_filters` | Yes | |
| UC-12 | Review history and duplicate | UC12 | Pass | `test_history.py` (4 tests) | Yes | |

## Data model (§6)

**DM-1: Pass.** All 25 entities have a model and a table, and `uv run alembic check` reports
no drift. `tests/test_constraints_sql.py` runs `tests/constraints/verify_constraints.sql`
against the migrated schema.

| SRS entity | Model | Table |
|---|---|---|
| User | `User` | `users` |
| Organizer Profile | `OrganizerProfile` | `organizer_profiles` |
| Event | `Event` | `events` |
| Venue | `Venue` | `venues` |
| Venue Section | `VenueSection` | `venue_sections` |
| Row | `Row` | `seat_rows` |
| Seat | `Seat` | `seats` |
| Seat Hold | `SeatHold` | `seat_holds` |
| Ticket Type | `TicketType` | `ticket_types` |
| Order | `Order` | `orders` |
| Order Item | `OrderItem` | `order_items` |
| Ticket | `Ticket` | `tickets` |
| Attendee | `Attendee` | `attendees` |
| Payment | `Payment` | `payments` |
| Refund | `Refund` | `refunds` |
| Payout Account | `PayoutAccount` | `payout_accounts` |
| Check-In Record | `CheckInRecord` | `check_in_records` |
| Staff Assignment | `StaffAssignment` | `staff_assignments` |
| Notification | `Notification` | `notifications` |
| Support Case | `SupportCase` | `support_cases` |
| Support Message | `SupportMessage` | `support_messages` |
| Promotional Campaign | `PromotionalCampaign` | `promotional_campaigns` |
| Promo Code | `PromoCode` | `promo_codes` |
| Promo Redemption | `PromoRedemption` | `promo_redemptions` |
| Audit Log | `AuditLogEntry` | `audit_log_entries` |

Extra models, not in §6: `PaidSalesActivation`, `PromoCodeTicketType`, `EventReport` and
`PlatformSettings` (each explained in `decisions.md`).

## Non-functional (§7)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| NFR-1 | Modern desktop and mobile browsers, 390px | §7 | Pass | Playwright `smoke.spec.ts` visits every route at desktop and 390×844 and fails on horizontal overflow | Yes | Chromium only. Safari and Firefox are in the manual checklist. |
| NFR-2 | Kazakh and Russian, English extra; no hard-coded strings and key parity *(team)* | §7 | Fixed ([#41](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/41), open) | key parity: `check-messages.mjs` (web, 712 keys), `check-locales.mjs` (scanner, 80 keys), `test_every_template_exists_in_kk_ru_en…`, `test_document_strings_have_the_same_keys_in_every_locale`; scanner: `i18n.test.ts` "has no hard-coded text in screens or components" | Yes | **Fixed by** `apps/web/scripts/check-hardcoded.mjs` in `npm run lint`. It found and fixed one case (the header nav's aria-label). Before: The SRS part passes. **Gap *(team)*: no hard-coded-string check for the web app.** The scanner has one, the web app doesn't. Not an SRS failure. Native proofreading is in the manual checklist. |
| NFR-3 | Integer KZT only | §7 | Pass | `money_kzt()` in `app/models/base.py`; no `Float` / `Numeric` in `app/models/`; `alembic check` | Yes | |
| NFR-4 | *(decision)* In transit via Caddy; at rest via host encryption, real at-rest deferred | §7 | Fixed ([#36](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/36), open) | `docker-compose.yml` has no proxy; `docs/https-proxy-proposal.md` is still "proposed" | No | **Fixed by** the Caddy service on `https://localhost:8443` (internal TLS), the Secure cookie behind HTTPS, and the at-rest note in the README; Playwright 8/8 through HTTPS. Before: **Fix:** the Caddy service ([#36](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/36)). At rest is a recorded decision (`decisions.md`); the README needs a line on it. |
| NFR-5 | Organizer and admin actions auditable | §7 | Pass | HIS-5, ADM-9, `test_audit.py` | Yes | |
| NFR-6 | Event pages meet WCAG 2.1 AA (axe through Playwright) | §7 | Fixed ([#39](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/39), open) | `@axe-core/playwright` isn't installed and no test runs axe | Partial (`design-direction.md` has a contrast table) | **Fixed by** `apps/web/e2e/accessibility.spec.ts` (axe, WCAG 2.0/2.1 A+AA, 30 page scans in kk/ru/en at desktop and 390px). It found and fixed one serious violation (WCAG 2.5.3 on the PDF button). Before: **Fix:** an axe Playwright spec for the event list, event, checkout and ticket pages. |
| NFR-7 | Checkout survives a spike: 50 checkouts on the last 10 tickets | §7 | Fixed ([#37](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/37), open) | `test_last_ticket_sold_once_under_concurrency`, `test_capacity_holds_across_ticket_types_under_concurrency` (small concurrent runs) | No | **Fixed by** `test_fifty_concurrent_checkouts_for_the_last_ten_tickets`: exactly 10 sold, 40 clean 409s, no 5xx. **One unreproduced hang** in 1 of 5 local full-suite runs; see the PR. Before: **Gap: no load test at the asked size.** **Fix:** a pytest/httpx asyncio test with 50 concurrent checkouts on 10 tickets: exactly 10 sold, every other response a clean 409, no 5xx. |
| NFR-8 | Architecture allows more currencies and languages; document how | §7 | Fixed ([#41](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/41), open) | `CURRENCY=KZT` setting, `*_kzt` columns; next-intl locales and `messages/*.json` | No | **Fixed by** "Adding currencies and languages later" in `decisions.md`. Before: **Gap: not documented.** **Fix:** a short `decisions.md` section on adding a locale (a messages file plus key parity) and a currency (a currency column plus migration; the `_kzt` naming is deliberate). |
| NFR-9 | Backup and restore script, run once | §7 | Pass | `scripts/backup-db.sh`, `scripts/restore-db.sh`; run on 2026-11-23 (see Checks run) | Yes | |
| NFR-10 | No secrets in the repo; history scan | §7 | Pass | gitleaks over 154 commits: 1 false positive (see Checks run); CI job `scripts/check-secrets.py` | Yes | |
| NFR-11 | *(team)* Login and sign-up rate limiting | — | Pass | `test_rate_limit.py` (6 tests) | Yes | |

## MVP delivery (§8, §9, §13)

| ID | Requirement | SRS § | Status | Evidence | Docs | Notes |
|---|---|---|---|---|---|---|
| DEL-1 | `docker compose up` runs db, api, web, mailpit, Caddy; seeding *(team)* | §8 | Fixed ([#36](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/36), open) | `docker compose up --build` healthy (see Checks run); seeding: `test_seed_is_idempotent` | Yes | **Fixed by** the Caddy service in a plain `docker compose up` (5 services healthy). Before: **Gap: no proxy service.** Fixed together with NFR-4. Seeding *(team)* passes. |
| DEL-2 | One backend, no needless microservices | §9 | Pass | `apps/api` is the only backend | Yes | |
| DEL-3 | Backend and DB choice with rationale | §9 | Partial ([#41](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/41), open) | `decisions.md`: "Python (FastAPI, async SQLAlchemy) and PostgreSQL 16" | Partial | Rationale added in `decisions.md`, but **the team-familiarity point is left for the team to fill in**, so this stays Partial until then. Before: **Gap: no rationale.** §9 asks for team familiarity, development speed, data-model needs and deployment complexity. **Fix:** a short rationale in `decisions.md`. |
| DEL-4 | API, interface, payment and QR tests in CI | §9 | Pass | `.github/workflows/ci.yml`: pytest, web lint/tsc/build, scanner jest, Playwright e2e; the last 3 runs on `main` passed | Yes | |
| DEL-5 | README: setup, every feature, demo flow; OpenAPI | §13.4 | Pass | README "Getting started", one API section per SRS area, "End-to-end test (Playwright)" with the core-flow steps; `docs/demo-report-3.md`; `/openapi.json` and `/docs` | Yes | |

## Excluded (§8)

**Excluded: confirmed, none present.** A search of `apps/api/app`, `apps/web/src` and
`apps/scanner/src` for resale, transfer, recurring events, affiliates, payout splits, KYC and
offline sync found only comments that say they're out of scope (`enums.py`, the payout
service). There are no real payouts or real money, no venue designer, no store publication,
no native attendee or organizer app, no marketing automation, no hardware integration, no tax
automation and no field-level version history. The seating models (§6) exist without any API,
which belongs to the bonus seating feature and isn't an exclusion.

## Part 2 fix plan

| Row(s) | Branch | Fix | Status |
|---|---|---|---|
| NFR-4, DEL-1 | `fix/srs-https-proxy` | Caddy service with internal TLS in front of web and api, the Secure cookie on HTTPS, README | [#36](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/36) |
| NFR-6 | `fix/srs-accessibility` | `@axe-core/playwright` (devDependency) and an axe spec for the event, checkout and ticket pages | [#39](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/39) |
| NFR-7 | `fix/srs-load-test` | 50 concurrent checkouts on 10 tickets | [#37](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/37) |
| PAY-9, ORD-6 | `fix/srs-payments-tests` | card-data and payment-audit tests | [#38](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/38) |
| ADM-7 | `fix/srs-admin-promotions` | admin promo-code activity endpoint, test and tab | [#40](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/40) |
| NFR-8, DEL-3 | `fix/srs-docs` | currency/language and stack-rationale notes in `decisions.md` | [#41](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/41) |
| NFR-2 *(team)* | `fix/srs-docs` | web hard-coded-string check like the scanner's | [#41](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/41) |

## Open decisions

1. **EVT-2 images.** Today an event has one cover image, by URL. Supporting uploads or several
   images needs a model change (a new migration) and file storage. Options: accept one cover
   URL for the MVP and record it in `decisions.md`, or mark it Deferred.
2. **ADM-5 disputes.** Treat support cases in the `payment` and `refund` categories as the
   MVP's disputes (admins can already see all of them), and record that? Or add a dispute
   filter to the admin portal?

## Totals (both parts)

Checked on 2026-11-23. 191 checklist rows, plus DM-1 (Pass) and the §8 exclusions (confirmed
absent).

| Status | Rows | Which |
|---|---|---|
| Pass | 154 | everything not listed below |
| Fixed | 15 | earlier in [#33](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/33): MOB-2, MOB-7, MOB-10. In this check: CORE-1, SC-1, UC-1 ([#35](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/35)); NFR-4, DEL-1 ([#36](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/36)); NFR-7 ([#37](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/37)); PAY-9, ORD-6 ([#38](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/38)); NFR-6 ([#39](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/39)); ADM-7 ([#40](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/40)); NFR-2 *(team)*, NFR-8 ([#41](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/41)) |
| Partial | 4 | EVT-2 and ADM-5 / ROLE-6 (waiting on the open decisions above); DEL-3 (the team has to write the familiarity point) |
| Missing | 0 | |
| Deferred | 0 | |
| Manual | 1 | MOB-11 (plus the manual checklist below) |
| Bonus–not built | 17 | SEAT-1..7, CAL-1..6, UC-6, UC-8, PRM-12 (GA4), SUP-10 |
| Bonus–built | 0 | |
| Excluded | confirmed | nothing from §8 is present |

"Fixed" rows link PRs that are **open, not merged**, with CI green at the time of writing.
Until they merge, `main` still has those gaps.

**Remaining gaps:**
1. EVT-2: one cover image by URL, no uploads or gallery. Needs a decision (open decision 1).
2. ADM-5 / ROLE-6: no explicit "dispute" view. Needs a decision (open decision 2).
3. DEL-3: the rationale is written ([#41](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/41)) except team familiarity, which only the team can fill in.
4. NFR-7 follow-up: one unreproduced test hang (1 of 5 local runs). The likely cause is the
   ticket PDFs rendering while the inventory row lock is held; see [#37](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/37).
5. The manual checklist below.

**PR links:** report [#34](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/34) · fixes [#35](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/35), [#36](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/36), [#37](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/37),
[#38](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/38), [#39](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/39), [#40](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/40), [#41](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/41).

**Merge notes:** [#35](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/35) and [#39](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/39) both edit `apps/web/e2e/core-flow.spec.ts`
(different lines). [#35](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/35), [#36](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/36), [#39](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/39), [#40](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/40) and [#41](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/41)
all edit the README, and [#39](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/39), [#40](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/40) and [#41](https://github.com/kadysmuktaruly/BiletFlow-project---Team-404-Not-Found-/pull/41) all edit
`apps/web/messages/*.json` (different keys). Each was branched from `main`, so whichever
merges later may need a quick rebase.

## Manual checklist

For the team. Tick Pass or Fail, and write your name and the date.

| # | Check | Pass / Fail | Tester | Date |
|---|---|---|---|---|
| 1 | Scanner on a real Android phone and a real iPhone, over mobile data (scanner M1, M6) | ☐ Pass ☐ Fail | | |
| 2 | Scanning a printed grayscale A4 ticket, a ticket on another phone's screen, and a Campaign QR, which must be rejected (scanner M2–M5) | ☐ Pass ☐ Fail | | |
| 3 | Time from scan to result, under 2 s (scanner M7) | ☐ Pass ☐ Fail | | |
| 4 | The full core flow done by hand in the demo stack, recorded as video | ☐ Pass ☐ Fail | | |
| 5 | Screen-reader and keyboard pass on the event, checkout and ticket pages | ☐ Pass ☐ Fail | | |
| 6 | Native-speaker proofreading of the Kazakh and Russian text | ☐ Pass ☐ Fail | | |
| 7 | A clean-machine install from the README alone, timed (target about 15 minutes) | ☐ Pass ☐ Fail | | |
| 8 | Safari and Firefox (desktop and iOS Safari) on the event, checkout and ticket pages (NFR-1) | ☐ Pass ☐ Fail | | |
