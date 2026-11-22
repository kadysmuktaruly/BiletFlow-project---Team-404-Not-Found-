import { expect, test, type APIRequestContext } from "@playwright/test";

/**
 * The live demo from the pitch, step by step, so a rehearsal can be checked in one command:
 * Aliya opens the Jazz Night, switches to Kazakh and back, buys one Standard ticket with
 * JAZZ15 through the DEMO payment, the ticket arrives in Mailpit with a PDF, My tickets shows
 * the QR full screen and offers the calendar file, and at the door the ticket is valid once,
 * then already used (with the time).
 *
 * Needs the stack with the demo seed (`docker compose up -d`). Mailpit's API defaults to
 * http://localhost:8025 (MAILPIT_URL to point elsewhere); the step is skipped when it isn't
 * reachable, as in CI.
 */

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const MAILPIT = process.env.MAILPIT_URL ?? "http://localhost:8025";
const PASSWORD = "Demo-pass-2026";
const ATTENDEE = "aliya@demo.biletflow.kz";
const STAFF = "staff@demo.biletflow.kz";
const JAZZ = "almaty-jazz-night-demo";

async function apiToken(request: APIRequestContext, email: string): Promise<string> {
  const response = await request.post(`${API}/api/v1/auth/login`, {
    data: { email, password: PASSWORD },
    headers: { "X-Client": "scanner" },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).access_token as string;
}

async function mailpitUp(request: APIRequestContext): Promise<boolean> {
  try {
    return (await request.get(`${MAILPIT}/api/v1/messages?limit=1`, { timeout: 2_000 })).ok();
  } catch {
    return false;
  }
}

test("pitch demo: Jazz Night with JAZZ15 → email with PDF → full-screen QR → door", async ({ page, request }) => {
  const mail = await mailpitUp(request);
  const startedAt = new Date();

  // Signed in before going on stage.
  await page.goto("/en/login");
  await page.getByLabel("Email").fill(ATTENDEE);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);

  // 1. "Here are the public events. Let's open the Jazz Night."
  await page.goto("/en/events");
  await page.getByRole("link", { name: /Almaty Jazz Night/ }).first().click();
  await expect(page).toHaveURL(new RegExp(`/en/events/${JAZZ}`));
  await expect(page.getByRole("heading", { name: "Almaty Jazz Night" })).toBeVisible();

  // 2. Switch the language to Kazakh and back.
  await page.getByRole("combobox", { name: "Language" }).selectOption("kk");
  await expect(page).toHaveURL(new RegExp(`/kk/events/${JAZZ}`));
  await expect(page.locator("html")).toHaveAttribute("lang", "kk");
  await page.getByRole("combobox", { name: "Тіл" }).selectOption("en");
  await expect(page).toHaveURL(new RegExp(`/en/events/${JAZZ}`));

  // 3. One ticket and JAZZ15: the server quotes 15% off (8,000 → 6,800 KZT).
  await page.getByRole("combobox", { name: "Quantity for Standard" }).selectOption("1");
  await page.getByLabel("Promo code").fill("JAZZ15");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByText(/Code JAZZ15 applied: −/)).toBeVisible();
  await expect(page.getByText(/6[\s,.  ]?800/).first()).toBeVisible();

  // 4. The DEMO payment, marked as such.
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Continue to payment" }).click();
  await expect(page).toHaveURL(/\/checkout\//);
  const pay = page.getByRole("button", { name: /Pay .* \(DEMO: succeeds\)/ });
  await expect(pay).toBeVisible();
  await expect(page.getByText("DEMO").first()).toBeVisible();
  await pay.click();
  await expect(page.getByRole("heading", { name: "You're going!" })).toBeVisible();
  const orderId = page.url().split("/orders/")[1];

  // 5. The ticket arrives by email straight away, with a PDF.
  if (mail) {
    await expect
      .poll(
        async () => {
          const list = await (
            await request.get(`${MAILPIT}/api/v1/search`, { params: { query: `to:${ATTENDEE}`, limit: "5" } })
          ).json();
          const fresh = (list.messages ?? []).find(
            (m: { Created: string; Attachments: number }) => new Date(m.Created) >= startedAt && m.Attachments > 0,
          );
          if (!fresh) return [];
          const message = await (await request.get(`${MAILPIT}/api/v1/message/${fresh.ID}`)).json();
          return (message.Attachments ?? []).map((a: { ContentType: string }) => a.ContentType);
        },
        { timeout: 20_000 },
      )
      .toContain("application/pdf");
  }

  // 6. My tickets: the QR full screen, and the event as a calendar file.
  await page.goto("/en/tickets");
  const fullScreen = page.getByRole("button", { name: /Show the QR code for ticket .* full screen/ }).first();
  await fullScreen.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const box = await dialog.getByRole("img").boundingBox();
  expect(box?.width ?? 0).toBeGreaterThan(400);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  const [ics] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: /Add Almaty Jazz Night to your calendar/ }).click(),
  ]);
  expect(ics.suggestedFilename()).toBe(`${JAZZ}.ics`);

  // At the door: valid once, then already used with the time it was checked in.
  const token = await apiToken(request, ATTENDEE);
  const order = await (
    await request.get(`${API}/api/v1/orders/${orderId}`, { headers: { Authorization: `Bearer ${token}` } })
  ).json();
  expect(order.promo_code).toBe("JAZZ15");
  const eventId = order.event.id as string;
  const staff = { Authorization: `Bearer ${await apiToken(request, STAFF)}` };
  const scan = async () =>
    (
      await request.post(`${API}/api/v1/checkin/events/${eventId}/scan`, {
        headers: staff,
        data: { payload: order.tickets[0].qr_payload },
      })
    ).json();
  expect((await scan()).result).toBe("valid");
  const again = await scan();
  expect(again.result).toBe("already_used");
  expect(again.ticket.checked_in_at).toBeTruthy();
});
