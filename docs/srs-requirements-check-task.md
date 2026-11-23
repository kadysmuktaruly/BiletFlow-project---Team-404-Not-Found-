# Task: verify the whole project against the SRS

The source text is `docs/srs/srs.md` (SRS v0.3). The authoritative copy is
`docs/srs/BiletFlow_SRS_v0.3.pdf`, for reference. This file lists every requirement in it. Check each
one against the code, with tests and the running stack, and produce an honest report. Then fix
what's broken or missing in the **required** scope.

The same autonomous rules and hard limits as before apply, plus everything in CLAUDE.md. Never
merge to main, never force-push (at all, per CLAUDE.md), and never edit
`0001_initial_schema.py`. Use no dependencies beyond the approved list.

**Approved dev-only / run-once tools** (they never ship in the app):
- DT-6: `pypdfium2` + `zxing` (already approved).
- NFR-6: `@axe-core/playwright` as a web devDependency.
- NFR-7: no new tool. The load test is a pytest/httpx asyncio script.
- NFR-10: `gitleaks`, run once through its Docker image. The output is recorded in the
  report and nothing is added to the repo.
- DEL-1 / NFR-4: Caddy as a compose service (a Docker image, not a library), following
  `docs/https-proxy-proposal.md`.

**Tags:**
- **(team)**: a team requirement, not in the SRS. A failure on it is not an SRS failure.
- **(decision)**: a recorded decision, listed in `docs/decisions.md`.

## How to check

1. Copy the checklist below into `docs/srs-compliance.md` as a table with these columns:
   **ID | Requirement | SRS § | Status | Evidence | Docs | Notes**. **Docs** is Yes or No for
   the row's feature area: is it documented in the README or `docs/`? (§13.4: a feature is
   done only when it is documented.) A row whose area has no docs is at most Partial.
2. Use exactly one status per row. The same set is used in
   `docs/scanner-requirements-check.md`:
   - **Pass**: implemented, covered by an automated test, and working in `docker compose up`.
   - **Fixed (PR link)**: was Partial or Missing, fixed by the linked PR, with a test.
   - **Partial**: exists but is incomplete, untested, undocumented or buggy (say exactly
     what's wrong).
   - **Missing**: not implemented.
   - **Deferred (reason)**: a required gap that can't land safely before the freeze, or a row
     not reached by Nov 28.
   - **Manual**: can only be verified by a person (add it to the manual checklist).
   - **Bonus–built** / **Bonus–not built**: only for items marked *(bonus)*.
   - **Excluded**: only for the §8 exclusions at the end. Confirm nothing excluded was built
     in a way that breaks scope.
3. Evidence means real proof: a test name plus file path, an endpoint, a component path, or
   a command you ran with its output. "Looks implemented" is not evidence. If an item has no
   test, it's Partial, not Pass.
4. For the scanner rows (MOB-*), reuse `docs/scanner-requirements-check.md` if it exists. Don't
   redo that work, just link it.
5. Run all checks and record the results at the top of the report: ruff check, ruff format
   --check, mypy, pytest, alembic check, web lint, tsc and tests, scanner lint, tsc and jest,
   Playwright, and `docker compose up --build` with a smoke test.

## Order and timing

Today is Nov 23 and the feature freeze is **Nov 29**. Check and report in this order:
1. CORE-1 and SC-1..SC-12. **Post the first report as soon as this section is done**, before
   the other rows.
2. Everything else, area by area.

Any row not reached by **Nov 28** is marked **Deferred (not reached before freeze)**.

## Then fix

- Fix every **Partial** and **Missing** in the required scope, in this order: the §13.4 core
  flow first (CORE-1), then the §11 success criteria, then everything else. Use one branch and PR
  per area (`fix/srs-<area>`). Each fix needs a test.
- Do **not** build *(bonus)* items that don't exist yet. Report them only.
- If a fix is too big to land safely before the Nov 29 feature freeze, mark it **Deferred**,
  explain why, and move on.
- Update `docs/srs-compliance.md` as fixes land (Fixed, with the PR link).
- Finish with a summary listing counts per status, every remaining gap, all PR links, and the
  manual checklist.

---

## Checklist

### Roles and structure (§1.3, §2.1, §2.3)
- **ROLE-1** There are four roles: Attendee, Organizer, Event Admin (assigned per event through
  StaffAssignment) and Platform Admin. Event Admin and Platform Admin are separate.
- **ROLE-2** Self-registration may choose only attendee or organizer. Platform admin is never
  self-assignable.
- **ROLE-3** The product consists of a responsive web app (organizers and attendees), an
  iOS/Android scanner app (Event Admins), an admin web portal, and a backend.
- **ROLE-4** Attendees can browse, register, purchase, download tickets and review their
  orders.
- **ROLE-5** Organizers can create events, configure ticket types, activate paid sales, manage
  attendees, view sales and assign check-in staff.
- **ROLE-6** Platform Admins can moderate events, manage users, review activation requests,
  handle disputes and view platform reports.

### Free and paid model (§3)
- **BIZ-1** Creating and publishing an event, free ticket types, QR tickets, attendee lists,
  check-in and confirmation messages all cost nothing.
- **BIZ-2** Paid sales stay disabled until all of these are done: an event with at least one
  paid ticket type, (simulated) identity and payout verification, the activation fee paid, a
  payout account set, and the paid-event terms accepted.
- **BIZ-3** Activation applies per event.
- **BIZ-4** Everything is simulation or sandbox and clearly labelled DEMO. No real money moves.
- **BIZ-5** The activation fee is a one-time charge per event in KZT, taken from
  `ACTIVATION_FEE_KZT` or platform settings.
- **BIZ-6** *(decision)* Processing charges are deducted from the organizer's estimated payout
  (SRS §3.3 says "deducted from each transaction" and §12 leaves the payer open). There is no
  per-ticket service fee.

### Accounts (§4.1)
- **ACC-1** Register with email.
- **ACC-2** Email verification, sent to Mailpit in dev.
- **ACC-3** Sign in, sign out and password reset. No response reveals whether an email is
  registered.
- **ACC-4** The organizer profile holds contact and payout info.
- **ACC-5** Role-based permissions are enforced server-side through reusable dependencies.
- **ACC-6** Passwords are stored with secure hashing (§7).

### Events (§4.2)
- **EVT-1** Organizers can create, edit, duplicate, publish, unpublish and cancel events.
- **EVT-2** An event has a title, description, category, **images**, venue, date and time.
  It also has an IANA timezone *(team)*.
- **EVT-3** Physical, venue-based events only.
- **EVT-4** Visibility is public, unlisted or private, and each one behaves correctly in
  listings and on direct links.
- **EVT-5** Registration has opening and closing times, which are enforced.
- **EVT-6** Event capacity is enforced.
- **EVT-7** An event can be previewed before publication.

### Tickets (§4.3)
- **TKT-1** Free and paid ticket types.
- **TKT-2** Each type has a name, description, price (integer KZT) and quantity.
- **TKT-3** Sales start and end times are enforced.
- **TKT-4** A per-order purchase limit is enforced.
- **TKT-5** Types can be hidden without being deleted.
- **TKT-6** Organizers see available, reserved, sold, refunded and checked-in counts per type.
- **TKT-7** Sales are blocked once inventory runs out. A concurrency test proves the last
  ticket can't be sold twice.

### Assigned seating (§4.3.1, §7) *(bonus)*
- **SEAT-1** *(bonus)* General admission or assigned seating can be chosen per event.
- **SEAT-2** *(bonus)* One predefined layout with sections, rows, seat numbers, accessible
  seats and price categories.
- **SEAT-3** *(bonus)* An interactive SVG seat map in which available, selected, held, sold,
  unavailable and accessible seats are each distinguished by color AND text or symbol.
  Usable on mobile and with a keyboard.
- **SEAT-4** *(bonus)* Temporary holds that expire. Reservation queries check `expires_at`.
- **SEAT-5** *(bonus)* No double-sold seat under concurrent checkout, and the section, row and
  seat are stored on both the ticket and the order item.
- **SEAT-6** *(bonus)* The organizer selects and configures the predefined layout (no visual
  editor).
- **SEAT-7** *(bonus)* The attendee selects one or more seats and sees the ticket price before
  continuing to checkout.

### Free registration (§4.4)
- **FREE-1** A free ticket can be reserved without any payment information.
- **FREE-2** The order total is zero.
- **FREE-3** A confirmation email with the QR ticket is sent.
- **FREE-4** The registration appears in the organizer's attendee list.

### Paid sales activation (§4.5)
- **ACT-1** Paid tickets can't be bought before activation, and the server enforces it.
- **ACT-2** The organizer sees an activation checklist.
- **ACT-3** Payment of the activation fee is recorded.
- **ACT-4** The system verifies that the simulated payout requirements are complete.
- **ACT-5** Activation applies only to the selected event.
- **ACT-6** A Platform Admin can suspend paid sales, and checkout stops immediately.

### Checkout and payments (§4.6)
- **PAY-1** The attendee selects tickets and gives attendee details.
- **PAY-2** Inventory is reserved during checkout and released when the reservation expires.
- **PAY-3** Totals and processing charges are calculated on the server.
- **PAY-4** Payment is simulated with success, failure and abandonment, labelled DEMO, and
  idempotent.
- **PAY-5** Tickets are issued only after payment is confirmed.
- **PAY-6** Failed or abandoned payments never create valid tickets.
- **PAY-7** Organizers see gross sales, fees, refunds and the estimated payout.
- **PAY-8** Demo payment records are never presented as real transactions.
- **PAY-9** Card data is never stored (§7).

### Digital and printable tickets (§4.7, §7)
- **DT-1** Each ticket has a unique ID, event and ticket-type info, attendee info, a
  tamper-resistant (signed) QR code, and a status: valid, checked in, cancelled or refunded.
- **DT-2** Tickets are available by email and in the attendee's account.
- **DT-3** A print-optimized A4 PDF can be downloaded.
- **DT-4** The PDF includes the event name, date and time, venue, ticket type, attendee name,
  section/row/seat if any, the ticket ID and the QR code.
- **DT-5** The PDF contains no payment data or other unnecessary sensitive information.
- **DT-6** The QR code scans from a grayscale print. Test it by rendering the PDF in grayscale
  and decoding the QR.
- **DT-7** The digital and printed copies share one ticket ID and can't be admitted twice.

### Scanner app (§4.8, §7, §10)
- **MOB-1** Secure sign-in. Only assigned events are shown.
- **MOB-2** Scans QR codes with the camera.
- **MOB-3** Validates authenticity and status in real time on the server.
- **MOB-4** Shows valid / invalid / cancelled / refunded / already used, with color and text.
- **MOB-5** Records check-ins atomically, with no double check-in.
- **MOB-6** Manual attendee search.
- **MOB-7** Authorized undo.
- **MOB-8** Registered and checked-in totals.
- **MOB-9** Online sync with the platform. Offline mode is *(bonus)*.
- **MOB-10** Validation in under 2 seconds.
- **MOB-11** Supports current iOS and Android. **Manual**: test on real devices.

### Orders, cancellations, refunds (§4.9)
- **ORD-1** Attendees can view their orders.
- **ORD-2** Organizers can define a refund policy.
- **ORD-3** Organizers can cancel free registrations.
- **ORD-4** Authorized organizers can issue full refunds through the simulation, idempotently.
- **ORD-5** Refunded or cancelled tickets become invalid and fail at check-in.
- **ORD-6** Every payment and refund action is in the audit log.
- **ORD-7** Cancelling an event cancels its tickets, notifies attendees and fully refunds paid
  orders (team decision).

### Notifications (§4.10)
Each needs an email and/or in-app notification, plus a test that it fires. kk/ru/en templates
for each are *(team)*.
- **NTF-1** Account verification
- **NTF-2** Registration or purchase confirmation
- **NTF-3** Payment failure
- **NTF-4** Ticket delivery
- **NTF-5** Event updates
- **NTF-6** Event cancellation
- **NTF-7** Refund completion
- **NTF-8** Organizer payout status
- **NTF-9** New support message, support-case assignment and status change
- **NTF-10** *(team)* An in-app notification list API and a notification center in the web
  app. (SRS §4.13 only asks for "in-app or email".)

### Calendar export (§4.11, §7) *(bonus)*
- **CAL-1** *(bonus)* `.ics` download.
- **CAL-2** *(bonus)* One-click Google and Outlook links on the event page and the order
  confirmation.
- **CAL-3** *(bonus)* Includes the title, start and end, time zone, venue name and address,
  description, and URL.
- **CAL-4** *(bonus)* A stable UID, so updates replace the earlier entry.
- **CAL-5** *(bonus)* A cancelled event produces an updated cancellation entry.
- **CAL-6** *(bonus)* No write access to anyone's calendar account.

### Administration (§4.12)
- **ADM-1** Search users, events, orders and payments.
- **ADM-2** Suspend users and events.
- **ADM-3** Review reported events.
- **ADM-4** Inspect paid-sales activation records.
- **ADM-5** Monitor refunds, disputes and payment failures.
- **ADM-6** Configure the activation fee and platform settings.
- **ADM-7** Review escalated support cases and promo-code activity.
- **ADM-8** Export basic operational reports. The CSV format is *(team)*.
- **ADM-9** Every admin action is audited (§7).

### Support (§4.13, §7)
- **SUP-1** Attendees can open a case from an event, order or ticket page.
- **SUP-2** Organizers can open platform-support cases (account, activation, payment,
  technical).
- **SUP-3** The user, event, order and ticket context is attached automatically.
- **SUP-4** Issue categories: ticket delivery, payment, refund, seating, event info, check-in,
  account, technical.
- **SUP-5** An asynchronous message thread refreshed by polling. No WebSockets are needed.
- **SUP-6** Attendee ↔ organizer staff conversations, and organizer ↔ Platform Admin
  conversations.
- **SUP-7** Staff can assign cases and set the status: Open, In Progress, Waiting for Customer,
  Resolved.
- **SUP-8** Users are notified of replies and status changes.
- **SUP-9** Case history is retained. Access is enforced by role and by relationship to the
  case (unauthorized → 404).
- **SUP-10** No attachments *(bonus)*.

### Promo codes and Campaign QR (§4.14, §7)
- **PRM-1** Organizers create campaigns per event.
- **PRM-2** A percentage or fixed-KZT discount, validity dates, max redemptions, and eligible
  ticket types.
- **PRM-3** A unique promo code and a Campaign QR code are generated.
- **PRM-4** The Campaign QR encodes an HTTPS event link with an opaque token, with no price or
  discount values in it.
- **PRM-5** Scanning it opens the event with the code pre-applied after server validation.
- **PRM-6** The attendee sees the code, the discount and the new total before paying.
- **PRM-7** Expired, disabled, exhausted and inapplicable codes are rejected with a clear
  message. Codes are case-insensitive.
- **PRM-8** Discounts are calculated on the server only. The redemption limit is atomic under
  concurrency, with a test.
- **PRM-9** The Campaign QR looks visibly different from a ticket QR.
- **PRM-10** The scanner app and the admission endpoint always reject Campaign QRs.
- **PRM-11** Exact per-campaign redemptions, orders, tickets sold, gross revenue, discount
  amount and net revenue are recorded.
- **PRM-12** GA4 *(optional)*: if it's present, no personal data is sent to it.

### Analytics (§4.15, §7)
- **ANL-1** Organizers see analytics only for the events they manage.
- **ANL-2** Capacity, sold, remaining and % sold.
- **ANL-3** Gross sales, discounts, refunds and net demo revenue in KZT.
- **ANL-4** Sales over time, from order timestamps.
- **ANL-5** Sales by ticket type.
- **ANL-6** Campaign redemptions, tickets per campaign and the resulting revenue.
- **ANL-7** Checked-in count, absent count and check-in %.
- **ANL-8** Filters for event, date range (default last 30 days) and ticket type.
- **ANL-9** Computed only from BiletFlow records. No extra checkout fields or demographics.
- **ANL-10** Analytics queries don't slow checkout or ticket issuance. Check that the queries
  are read-only and take no locks.
- **ANL-11** On a seeded event, the dashboard numbers match the raw records. Write a test.

### Event history and audit (§4.16, §7)
- **HIS-1** Upcoming, Active, Completed and Cancelled views.
- **HIS-2** Past events open read-only with their tickets, orders, refunds, check-ins,
  campaigns, cases and analytics.
- **HIS-3** Duplicating an event creates a draft, without copying orders, tickets, payments,
  check-ins or cases.
- **HIS-4** A chronological activity timeline per event.
- **HIS-5** The timeline includes publish/cancel, price and capacity changes, refunds, promo
  create/disable, support status changes, check-ins and check-in reversals.
- **HIS-6** Each entry has a timestamp, acting user, action type, affected entity and
  description.
- **HIS-7** Filters by date range and activity type.
- **HIS-8** Only authorized event staff can see it, and Platform Admins can too.
- **HIS-9** Audit entries can't be edited or deleted through organizer interfaces (SRS
  §4.16). *(decision, beyond the SRS)*: the audit log is append-only at the database level,
  with a test that UPDATE and DELETE are blocked.

### Use cases end to end (§5)
Each one needs an automated test, as API or Playwright:
- **UC-1** An organizer creates and publishes a free event.
- **UC-2** An organizer activates paid sales.
- **UC-3** An attendee buys a ticket.
- **UC-4** An Event Admin checks an attendee in, and a second scan is rejected until the
  check-in is undone.
- **UC-5** An organizer refunds an order; the ticket becomes invalid and the attendee is
  notified.
- **UC-6** *(bonus)* An attendee adds the event to a calendar.
- **UC-7** An attendee prints a ticket and it scans.
- **UC-8** *(bonus)* An attendee picks an assigned seat.
- **UC-9** An attendee asks for support and the organizer replies.
- **UC-10** An attendee buys through a Campaign QR, and the sale is attributed to the
  campaign.
- **UC-11** An organizer reviews analytics with filters.
- **UC-12** An organizer reviews history and duplicates an event.

### Data model (§6)
- **DM-1** All 25 SRS entities exist as models. List each SRS entity against its model and
  table name.

### Non-functional (§7)
- **NFR-1** Works in modern desktop and mobile browsers, including at 390px width.
- **NFR-2** The customer-facing UI is in Kazakh and Russian, with English as an extra locale.
  No hard-coded strings and a kk/ru/en key-parity check are *(team)*.
- **NFR-3** All money is integer KZT. No floats or decimals anywhere.
- **NFR-4** *(decision)* SRS §7 asks for encryption in transit **and at rest**. In transit:
  HTTPS through Caddy (internal TLS) in the demo stack, which is a fix item. At rest: rely
  on the host's volume or disk encryption, and document that real at-rest encryption is
  deferred.
- **NFR-5** Organizer and admin actions are auditable.
- **NFR-6** Event pages meet WCAG 2.1 AA. Run axe through Playwright and record the results.
- **NFR-7** Checkout survives a traffic spike. Run a simple load test (e.g. 50 concurrent
  checkouts against the last 10 tickets) and confirm there's no overselling and no 500
  errors.
- **NFR-8** The architecture allows for future currencies and languages. Document how.
- **NFR-9** A backup and restore script exists and has been run once successfully.
- **NFR-10** No secrets are in the repo. Run a scan of the git history and report the result.
- **NFR-11** *(team)* Rate limiting on login and sign-up.

### MVP delivery (§8, §9, §13)
- **DEL-1** `docker compose up` runs the full stack (db, api, web, mailpit, Caddy proxy). The
  Caddy service is a fix item. Seeding demo data is *(team)*.
- **DEL-2** There is one backend (FastAPI) and no unnecessary microservices.
- **DEL-3** The backend and database choice is documented with a short rationale (team
  familiarity, speed, data model, deployment) in the README or `docs/`.
- **DEL-4** Automated API, interface, payment and QR-validation tests all run in CI.
- **DEL-5** The README documents setup, every feature and the demo flow. The OpenAPI reference
  is available.

### Core flow (§13.4) and success criteria (§11)
- **CORE-1** One Playwright run covers the full core flow: create event → Campaign QR → promo
  applied → ticket reserved → simulated checkout → ticket issued → support request → entry
  verified (through the API the scanner uses).
- **SC-1** An organizer publishes a free event and distributes valid tickets.
- **SC-2** An organizer completes the simulated activation and receives demo orders.
- **SC-3** An attendee checks out and receives a QR ticket.
- **SC-4** An attendee downloads and prints a ticket that scans.
- **SC-5** An Event Admin validates tickets and duplicate entry is prevented.
- **SC-6** An attendee opens a contextual support case and exchanges messages with organizer
  staff.
- **SC-7** An attendee scans a Campaign QR, gets the discount, and the order is attributed to
  the campaign.
- **SC-8** The scanner rejects Campaign QRs and still accepts valid tickets.
- **SC-9** Organizers see accurate ticket, attendance, payment and refund records.
- **SC-10** Organizers see sales, capacity, campaign and attendance analytics with no extra
  checkout fields.
- **SC-11** Organizers review past and cancelled events and the timeline, and duplicate events
  without copying transactions.
- **SC-12** An admin suspends a suspicious event and further sales stop.

### Excluded (§8). Confirm none are present or half-built.
Real payouts or real money; production KYC; a venue-layout designer; production offline sync;
advanced dispute workflows; store publication; resale or transfer; native attendee or
organizer apps; affiliate marketing; recurring events; marketing automation; hardware
integrations; split payouts; tax automation; field-level version history or rollback.

---

## Manual checklist

Put this at the end of `docs/srs-compliance.md`, for the team. Give each item a pass/fail box,
a tester name and a date:
- Scanner on a real Android phone and a real iPhone, over mobile data.
- Scanning a printed grayscale A4 ticket, a ticket on another phone's screen, and a Campaign
  QR (must be rejected).
- Time from scan to result (under 2 s).
- The full core flow done by hand in the demo stack, recorded as video evidence.
- Screen-reader and keyboard pass on the event, checkout and ticket pages.
- Proofreading of the Kazakh and Russian text by a native speaker.
- A clean-machine install from the README alone, timed (target ~15 minutes).
