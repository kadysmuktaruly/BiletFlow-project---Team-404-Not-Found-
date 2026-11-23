# Web redesign checklist

Every route of `apps/web` and the main actions on it. The redesign (see
[`design-direction.md`](design-direction.md)) may change only the presentation. Each row must
behave exactly as before. All routes are prefixed with the locale (`/kk`, `/ru`, `/en`).

`apps/web/e2e/smoke.spec.ts` opens every route below that has a smoke name, in kk, ru and en,
at 1280px and 390px, and checks the key heading, fields and buttons by role or label. It also
fails if the page scrolls sideways. With `SHOTS_DIR` set, it saves a full-page screenshot of
each one. `apps/web/e2e/core-flow.spec.ts` runs the full purchase flow through these screens.

| Route | Who | Main actions | Smoke name |
|---|---|---|---|
| `/` | anyone | Go to the event list, go to registration | `home` |
| `/events` | anyone | Search events (`?q=`), open an event | `events` |
| `/events/[slug]` | anyone | Choose quantities, apply or remove a promo code, continue to attendee details, place the order or reserve and go to checkout; signed in: get help, report the event | `event-detail` |
| `/c/[token]` | anyone | Campaign QR landing: the server resolves the token and redirects to the event with `?promo=` | (core flow) |
| `/login` | anonymous | Sign in, then return to `?next=`; links to forgot password and register | `login` |
| `/register` | anonymous | Create an account as attendee or organizer | `register` |
| `/verify-email` | anonymous | Confirm the email from `?token=`, ask for a new link | `verify-email` |
| `/forgot-password` | anonymous | Ask for a reset link | `forgot-password` |
| `/reset-password` | anonymous | Set a new password from `?token=` | `reset-password` |
| `/checkout/[orderId]` | buyer | DEMO pay (succeeds), DEMO pay (fails), cancel and release the tickets; DEMO badge and banner | `checkout` |
| `/orders/[orderId]` | buyer | Confirmation ("You're going!"), tickets with QR codes, download each PDF, refund or cancel where allowed, get help | `order` |
| `/orders` | signed in | List my orders, open one | `my-orders` |
| `/tickets` | signed in | My tickets with QR codes, download the PDF | `my-tickets` |
| `/notifications` | signed in | Read notifications, mark one or all as read, open the linked page | `notifications` |
| `/account` | signed in | See the account type; switch between attendee and organizer (with a confirmation; blocked while the organizer has live events) | `account` |
| `/support` | signed in | List cases (opened and handled), open one, start a new one | `support-list` |
| `/support/new` | signed in | Open a case (category, subject, message), with context from `?event=` / `?order=` / `?ticket=` | `support-new` |
| `/support/[caseId]` | case participant | Read the thread, reply; handlers: internal notes, status, assignment | `support-case` |
| `/organizer/events` | organizer | List events with a status filter, open one, create one | `organizer-events` |
| `/organizer/events/new` | organizer | Create a draft event (form) | `organizer-new-event` |
| `/organizer/profile` | organizer | Save the organizer profile; save the DEMO payout account | `organizer-profile` |
| `/organizer/analytics` | organizer | KPI cards, sales charts, filters (event, dates, ticket type), campaign and attendance tables | `organizer-analytics` |
| `/organizer/events/[id]` | owner | Edit details; publish, unpublish, cancel, duplicate; open the public page; contact platform support | `organizer-event-details` |
| `/organizer/events/[id]/tickets` | owner | Add, edit and remove ticket types | `organizer-event-tickets` |
| `/organizer/events/[id]/activation` | owner | DEMO paid-sales activation steps and fee | `organizer-event-activation` |
| `/organizer/events/[id]/staff` | owner | Add and remove check-in staff | `organizer-event-staff` |
| `/organizer/events/[id]/preview` | owner | Preview the public page | `organizer-event-preview` |
| `/organizer/events/[id]/campaigns` | owner | Create a campaign, copy its link, download the QR (SVG) or poster (PDF), disable it | `organizer-event-campaigns` |
| `/organizer/events/[id]/attendees` | owner | Search and filter attendees, live status | `organizer-event-attendees` |
| `/organizer/events/[id]/orders` | owner | Search and filter orders, DEMO refund, cancel a free registration | `organizer-event-orders` |
| `/organizer/events/[id]/analytics` | owner | The event's analytics | `organizer-event-analytics` |
| `/organizer/events/[id]/history` | owner | The activity timeline with filters | `organizer-event-history` |
| `/admin` | platform admin | Tabs: overview, users, events, orders, payments, paid sales, reports, settings; search, suspend or resume, export CSV, the activation fee | `admin` |

## Baseline (before the redesign, branch `feat/r6-web-redesign` at `dd3cc02`)

| Check | Result |
|---|---|
| `npm run lint -w @biletflow/web` (eslint + i18n key check) | pass, 708 keys in kk, ru, en |
| `npm run typecheck -w @biletflow/web` | pass |
| Web unit tests | none exist |
| `npm run build -w @biletflow/web` | pass |
| `playwright test core-flow` | 1 passed |
| `playwright test smoke` (32 routes × 3 locales × 2 sizes) | 4 passed, no horizontal overflow |

## After the redesign

| Check | Result |
|---|---|
| `npm run lint -w @biletflow/web` (eslint + i18n key check) | pass, 708 keys in kk, ru, en (unchanged) |
| `npm run typecheck -w @biletflow/web` | pass |
| `npm run build -w @biletflow/web` | pass |
| `playwright test core-flow` | 1 passed |
| `playwright test smoke` (32 routes × 3 locales × 2 sizes) | 4 passed, no horizontal overflow |
| Keyboard focus (events, event detail, login) | every focus stop has the 3px `sky-ink` outline |
| Contrast | every text/UI pair in `design-direction.md` passes AA (axe isn't installed, so this was checked against the table) |
| API: ruff, ruff format, mypy, pytest | pass (245 tests) |
