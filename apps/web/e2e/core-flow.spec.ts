import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * The SRS 13.4 core flow, end to end against the demo seed's accounts:
 * the organizer creates an event, adds a paid ticket type, activates paid sales (DEMO),
 * publishes and assigns door staff → creates a campaign → the attendee opens its Campaign QR
 * link → the promo code is applied → buys a ticket with the DEMO payment → confirmation, PDF
 * and support → the door admits the ticket once and rejects the Campaign QR → the sale shows
 * up in the organizer's analytics.
 *
 * The scanner is a native app, so the door step calls the same check-in API it uses.
 */

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const PASSWORD = "Demo-pass-2026";
const ORGANIZER = "organizer@demo.biletflow.kz";
const ATTENDEE = "timur@demo.biletflow.kz";
const STAFF = "staff@demo.biletflow.kz";

async function signIn(page: Page, email: string) {
  await page.goto("/en/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

async function apiToken(request: APIRequestContext, email: string): Promise<string> {
  const response = await request.post(`${API}/api/v1/auth/login`, {
    data: { email, password: PASSWORD },
    headers: { "X-Client": "scanner" },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).access_token as string;
}

test("create event → campaign QR → promo purchase → ticket → door → analytics", async ({ browser, request }) => {
  const code = `E2E${Date.now().toString(36).toUpperCase()}`.slice(0, 20);
  const year = new Date().getFullYear() + 1;

  // 0. The organizer creates an event in the UI and gets it ready to sell.
  const organizer = await browser.newPage();
  await signIn(organizer, ORGANIZER);
  await organizer.goto("/en/organizer/events/new");
  await organizer.getByRole("textbox", { name: "Title", exact: true }).fill(`E2E core flow ${code}`);
  await organizer.getByRole("textbox", { name: "Venue name", exact: true }).fill("Kazakhconcert Hall");
  await organizer.getByRole("textbox", { name: "Address", exact: true }).fill("Abay Ave 1");
  await organizer.getByRole("textbox", { name: "City", exact: true }).fill("Almaty");
  await organizer.getByRole("textbox", { name: "Starts", exact: true }).fill(`${year}-05-20T19:00`);
  await organizer.getByRole("textbox", { name: "Ends", exact: true }).fill(`${year}-05-20T22:00`);
  await organizer.getByRole("button", { name: "Save draft" }).click();
  await expect(organizer).toHaveURL(/\/organizer\/events\/[0-9a-f-]+\/tickets/);
  const eventId = organizer.url().split("/events/")[1].split("/")[0];

  // A paid ticket type.
  await organizer.getByLabel("Name", { exact: true }).fill("Standard");
  await organizer.getByLabel(/^Price, KZT/).fill("10000");
  await organizer.getByLabel(/^Quantity/).fill("50");
  await organizer.getByRole("button", { name: "Add ticket type" }).click();
  await expect(organizer.getByText("Standard").first()).toBeVisible();

  // Paid-sales activation: every DEMO step on the checklist.
  await organizer.goto(`/en/organizer/events/${eventId}/activation`);
  for (const step of ["Run simulated check", "Connect payout account", "Accept terms", "Pay (DEMO: succeeds)"]) {
    await organizer.getByRole("button", { name: step }).click();
    await expect(organizer.getByRole("button", { name: step })).toHaveCount(0);
  }
  await expect(organizer.getByText("Paid sales are on.")).toBeVisible();

  // Publish, and give the scanner account door access to this event.
  await organizer.getByRole("button", { name: "Publish" }).click();
  await expect(organizer.getByText("The event is live.")).toBeVisible();
  await organizer.goto(`/en/organizer/events/${eventId}/staff`);
  await organizer.getByLabel("Their BiletFlow email").fill(STAFF);
  await organizer.getByRole("button", { name: "Add to staff" }).click();
  await expect(organizer.getByText(STAFF)).toBeVisible();

  // 1. The organizer creates a 20% campaign on the new event.
  await organizer.goto(`/en/organizer/events/${eventId}/campaigns`);
  await organizer.getByLabel("Campaign name").fill(`E2E ${code}`);
  await organizer.getByLabel(/Promo code/).fill(code);
  await organizer.getByLabel("Percent off").fill("20");
  await organizer.getByRole("button", { name: "Create campaign" }).click();
  const card = organizer.locator("li", { hasText: code });
  await expect(card.getByText("Active")).toBeVisible();
  await expect(card.getByText(/Promo, not a ticket/i)).toBeVisible();
  const campaignUrl = (await card.locator("span.font-mono", { hasText: "/c/BFC1." }).innerText()).trim();
  expect(campaignUrl).toMatch(/\/c\/BFC1\./);

  // 2. The attendee opens the Campaign QR link: the event opens with the code applied.
  const attendee = await browser.newPage();
  await signIn(attendee, ATTENDEE);
  await attendee.goto(new URL(campaignUrl).pathname);
  await expect(attendee).toHaveURL(new RegExp(`/events/[^/?]+\\?promo=${code}`));
  await attendee.getByRole("combobox", { name: "Quantity for Standard" }).selectOption("1");
  await expect(attendee.getByText(new RegExp(`Code ${code} applied: −`))).toBeVisible();
  await expect(attendee.getByText(`Discount (${code})`).filter({ visible: true }).first()).toBeVisible();

  // 3. Checkout with the DEMO payment.
  await attendee.getByRole("button", { name: "Continue", exact: true }).click();
  await attendee.getByRole("button", { name: "Continue to payment" }).click();
  await expect(attendee).toHaveURL(/\/checkout\//);
  // Wait for something only the checkout page has; the event page may still be leaving.
  const pay = attendee.getByRole("button", { name: /Pay .* \(DEMO: succeeds\)/ });
  await expect(pay).toBeVisible();
  await expect(attendee.getByText("DEMO").first()).toBeVisible();
  await expect(attendee.getByText(`Discount (${code})`).filter({ visible: true }).first()).toBeVisible();
  await pay.click();
  await expect(attendee.getByRole("heading", { name: "You're going!" })).toBeVisible();
  const orderUrl = attendee.url();
  await expect(attendee.getByText(`Discount (${code})`).filter({ visible: true }).first()).toBeVisible();

  // 4. The printable PDF and a support case from the order.
  const [pdf] = await Promise.all([
    attendee.waitForEvent("download"),
    attendee.getByRole("button", { name: /Download ticket .* as a PDF/ }).first().click(),
  ]);
  expect(pdf.suggestedFilename()).toMatch(/^ticket-BFT-.*\.pdf$/);
  await attendee.getByRole("link", { name: "Get help" }).click();
  await attendee.getByLabel("Subject").fill("E2E: question about my ticket");
  await attendee.getByLabel("Message").fill("Can I bring a friend on the same ticket?");
  await attendee.getByRole("button", { name: "Send" }).click();
  await expect(attendee.getByText("Can I bring a friend on the same ticket?")).toBeVisible();

  // 5. At the door (the scanner's API): valid once, then already used; a Campaign QR is never a ticket.
  const attendeeToken = await apiToken(request, ATTENDEE);
  const orderId = orderUrl.split("/orders/")[1];
  const order = await (await request.get(`${API}/api/v1/orders/${orderId}`, { headers: { Authorization: `Bearer ${attendeeToken}` } })).json();
  const payload = order.tickets[0].qr_payload as string;
  expect(order.promo_code).toBe(code);
  const staff = { Authorization: `Bearer ${await apiToken(request, STAFF)}` };
  const scan = (p: string) => request.post(`${API}/api/v1/checkin/events/${eventId}/scan`, { headers: staff, data: { payload: p } });
  expect((await (await scan(payload)).json()).result).toBe("valid");
  expect((await (await scan(payload)).json()).result).toBe("already_used");
  const promo = await (await scan(campaignUrl)).json();
  expect([promo.result, promo.reason]).toEqual(["invalid", "campaign_qr_not_admission"]);

  // 6. The organizer's analytics count the campaign's redemption.
  await organizer.goto(`/en/organizer/events/${eventId}/analytics`);
  const row = organizer.getByRole("row", { name: new RegExp(code) });
  await expect(row).toBeVisible();
  await expect(row.getByRole("cell").nth(1)).toHaveText("1"); // redemptions
});
