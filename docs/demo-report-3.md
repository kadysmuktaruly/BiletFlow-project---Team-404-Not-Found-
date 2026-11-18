# Report 3 demo: free registration, DEMO paid purchase, QR ticket by email

This script shows the Report 3 checkpoint on a fresh stack: an attendee registers for a free
event, buys a paid ticket through the DEMO payment simulation, and receives the confirmation
email with QR tickets in Mailpit. It takes about 10 minutes.

The same flow is automated over the API in
`apps/api/tests/e2e/test_report3_flow.py` (runs in CI).

## 0. Before you start

- Docker Desktop with **at least 4 GB of memory** available to Docker (Settings → Resources).
  Building the web image needs about 1 GB. If other projects' containers are running, stop
  them or raise the limit.
- Ports 3000 (web), 8000 (API), 8025 and 1025 (Mailpit) and 5433 (Postgres) must be free.
  If 3000 is taken, see "Port 3000 is busy" at the end.

## 1. Start a fresh stack

```bash
cp .env.example .env              # optional; the defaults work without it
docker compose down -v            # WARNING: deletes the local BiletFlow database volume
docker compose up -d --build
docker compose ps                 # wait until db, api, web and mailpit are all "healthy"
```

On start the API applies migrations and loads the demo data (`SEED_DEMO_DATA=true`). The API
log ends with the demo accounts:

```bash
docker compose logs api | grep -A4 "Demo data ready"
```

| Account | Password | Role |
|---|---|---|
| `organizer@demo.biletflow.kz` | `Demo-pass-2026` | Organizer of both demo events |
| `attendee@demo.biletflow.kz` | `Demo-pass-2026` | Attendee with existing tickets |
| `staff@demo.biletflow.kz` | `Demo-pass-2026` | Event Admin on both events (scanner) |
| `admin@demo.biletflow.kz` | `Demo-pass-2026` | Platform Admin |

Demo events: **Student Tech Meetup** (free) and **Almaty Jazz Night** (paid: Standard
8,000 KZT, VIP 20,000 KZT; paid sales already activated through the DEMO checklist).

## 2. Create an attendee account and verify the email

1. Open http://localhost:3000. You land on `/kk` (Kazakh) or your browser's language. Use the
   language menu in the header to switch between Қазақша, Русский and English.
2. **Create account** → enter a name, a new email (any address works; mail never leaves
   Mailpit), a password of 8+ characters, and keep **Attend events**. Submit.
   *Expected:* "Check your inbox".
3. Open Mailpit at http://localhost:8025. Open **"Confirm your BiletFlow email"** and click
   **Confirm email**. *Expected:* "Your email is confirmed".
4. **Sign in** with the new account. *Expected:* your name and **Sign out** in the header.

## 3. Free registration

1. **Events** → **Student Tech Meetup**.
2. Set **Free registration** to `1` → **Continue**. Your name is filled in → **Get tickets**.
3. *Expected:* "You're going!" with one QR code, a ticket number like `BFT-XXXX-XXXX`,
   status **Confirmed** and "Free registration".

## 4. DEMO paid purchase

1. **Events** → **Almaty Jazz Night**. Set **Standard** to `2` → **Continue**.
2. Fill in the second attendee's name → **Continue to payment**.
3. *Expected:* the **DEMO payment** page with a yellow DEMO banner ("No card details are
   collected and no real money moves"), the order total of 16,000 KZT, and the time the
   tickets are held until (10 minutes).
4. Click **Pay KZT 16,000 (DEMO: succeeds)**.
5. *Expected:* "You're going!" with two QR codes and "Paid with a DEMO payment. No real money
   was charged."
6. **My tickets** shows all three tickets with their QR codes, grouped by event.

## 5. The confirmation emails in Mailpit

In http://localhost:8025 the new account now has two **"Your tickets: …"** emails:

- the free one says "Free registration. No payment needed." and shows one QR code;
- the paid one shows two QR codes (inline images, one per ticket) and says
  "DEMO payment: 16 000 KZT. This is a simulation; no real money was charged."

Each QR code encodes the ticket's signed admission token (`BFT1.…`). It's the same code shown
under My tickets.

## 6. Optional: the other payment outcomes

- **Failure:** buy a **VIP** ticket → **Simulate a failed payment**. *Expected:* "The DEMO
  payment failed…", no tickets, and a "DEMO payment failed" email. The VIP count goes back up.
- **Abandon:** start another purchase → **Cancel and release tickets**. *Expected:* "Order
  cancelled", and the tickets are back on sale at once.
- **Expiry:** start a purchase and leave the payment page open for 10 minutes. The order
  expires and paying returns "Your reservation expired…".

## 7. Optional: the organizer side

Sign in as `organizer@demo.biletflow.kz` → **My events** → **Almaty Jazz Night** → **Edit**:

- **Tickets**: live counts (available, reserved, sold, refunded, checked in), including the
  purchases you just made.
- **Paid sales**: the DEMO activation checklist, all five steps done, status **Active**.
- **Staff**: Madina Ospanova assigned as Event Admin (she signs in to the scanner app).
- **Preview**: the public page as attendees see it.

To see the paid-sales gate, create a new event, add a paid ticket type and publish it. The
public page says "Paid tickets aren't on sale yet" until the checklist is complete.

## 8. The same checks over the API (optional)

```bash
curl -s localhost:8000/api/v1/health                      # {"status":"ok","database":"ok"}
curl -s localhost:8000/api/v1/events | python3 -m json.tool | head -20
open http://localhost:8000/docs                           # interactive OpenAPI docs
```

## Troubleshooting

- **Port 3000 is busy.** Publish the web app elsewhere and point email links and CORS at it:
  `WEB_PORT=3100 PUBLIC_BASE_URL=http://localhost:3100 docker compose up -d --build`.
- **The web image build stops with exit code 137.** Docker ran out of memory. Give Docker
  more memory or stop other containers, then build again.
- **No email in Mailpit.** Check `docker compose logs api | grep -i email`. Mail is sent just
  after the request completes, so refresh Mailpit after a second.
- **"Paid tickets for this event aren't on sale yet."** That event's paid-sales checklist isn't
  complete (organizer → event → Paid sales). The seeded jazz night is already activated.

## What was checked, and how

| Step | Automated check |
|---|---|
| Sign-up, verification email, sign-in | `tests/test_auth.py`, `tests/e2e/test_report3_flow.py` |
| Free registration issues tickets at once | `tests/test_orders.py::test_free_order_zero_total_issues_tickets` |
| DEMO payment succeeds, fails, abandoned, expired | `tests/test_payments.py` |
| Confirmation email with inline QR per ticket | `tests/test_payments.py::test_successful_payment_issues_tickets_and_emails_qr` |
| Last ticket never sold twice | `tests/test_inventory_concurrency.py` |
| The browser flow above (steps 2–7) | Run once with a headless browser against the Compose API (see PR #12) |
