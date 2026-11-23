import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/**
 * SRS 7: "Event pages should meet WCAG 2.1 AA accessibility guidelines" (SRS compliance check
 * NFR-6). axe-core checks the attendee pages of the core flow (event list, event page, DEMO
 * checkout, order confirmation and My tickets) against the WCAG 2.0/2.1 A and AA rules, in
 * all three locales, at desktop and 390px. Automated rules catch roughly a third of WCAG
 * issues; the screen-reader and keyboard pass is in the manual checklist
 * (docs/srs-compliance.md).
 */

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const PASSWORD = "Demo-pass-2026";
const ATTENDEE = "aliya@demo.biletflow.kz";
const JAZZ = "almaty-jazz-night-demo";
const WCAG_AA = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const LOCALES = ["en", "kk", "ru"] as const;
const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844 },
];

async function expectNoViolations(page: Page, label: string) {
  // Wait for client-side data to render before scanning.
  await page.waitForLoadState("networkidle");
  const results = await new AxeBuilder({ page }).withTags(WCAG_AA).analyze();
  // Guard against a vacuous pass (e.g. scanning a blank or still-loading page).
  expect(results.passes.length, `${label}: axe checked too few rules`).toBeGreaterThan(10);
  const summary = results.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.help}\n    ${v.nodes.map((n) => n.target.join(" ")).join("\n    ")}`,
  );
  expect(summary, `${label}: WCAG 2.1 AA violations`).toEqual([]);
}

async function signIn(page: Page) {
  await page.goto("/en/login");
  await page.getByLabel("Email").fill(ATTENDEE);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

for (const viewport of VIEWPORTS) {
  test(`axe: public event pages, ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    for (const locale of LOCALES) {
      await page.goto(`/${locale}/events`);
      await expectNoViolations(page, `/${locale}/events (${viewport.name})`);
      await page.goto(`/${locale}/events/${JAZZ}`);
      await expectNoViolations(page, `/${locale}/events/${JAZZ} (${viewport.name})`);
    }
  });
}

test("axe: checkout, confirmation and tickets", async ({ page, request }) => {
  await signIn(page);
  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport);

    // A paid Standard ticket, reserved through the API with the same sign-in.
    const login = await request.post(`${API}/api/v1/auth/login`, {
      data: { email: ATTENDEE, password: PASSWORD },
      headers: { "X-Client": "scanner" },
    });
    expect(login.ok()).toBeTruthy();
    const auth = { Authorization: `Bearer ${(await login.json()).access_token}` };
    const event = await (await request.get(`${API}/api/v1/events/${JAZZ}`)).json();
    const standard = event.ticket_types.find((t: { name: string }) => t.name === "Standard");
    const order = await (
      await request.post(`${API}/api/v1/orders`, {
        headers: auth,
        data: { event_id: event.id, items: [{ ticket_type_id: standard.id, quantity: 1 }] },
      })
    ).json();
    expect(order.status).toBe("awaiting_payment");

    for (const locale of LOCALES) {
      await page.goto(`/${locale}/checkout/${order.id}`);
      await expectNoViolations(page, `/${locale}/checkout (${viewport.name})`);
    }
    await page.goto(`/en/checkout/${order.id}`);
    await page.getByRole("button", { name: /Pay .* \(DEMO: succeeds\)/ }).click();
    await expect(page.getByRole("heading", { name: "You're going!" })).toBeVisible();
    for (const locale of LOCALES) {
      await page.goto(`/${locale}/orders/${order.id}`);
      await expectNoViolations(page, `/${locale}/orders/[id] (${viewport.name})`);
      await page.goto(`/${locale}/tickets`);
      await expectNoViolations(page, `/${locale}/tickets (${viewport.name})`);
    }
  }
});
