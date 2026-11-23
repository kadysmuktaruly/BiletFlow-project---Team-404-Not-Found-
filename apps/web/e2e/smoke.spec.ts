import { expect, test, type APIRequestContext, type Browser, type Page } from "@playwright/test";

import en from "../messages/en.json";

/**
 * One smoke check per web route against the demo seed: the page renders its key heading,
 * fields and buttons (found by role or label, never by CSS class), in en, kk and ru, at
 * desktop and 390px mobile width, without horizontal overflow.
 *
 * SHOTS_DIR=../../.screenshots/before npm run e2e -w @biletflow/web -- smoke
 * also saves a full-page screenshot of every route and size (that folder is git-ignored).
 * The routes and their main actions are listed in docs/redesign-checklist.md.
 */

const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const SHOTS_DIR = process.env.SHOTS_DIR;
const PASSWORD = "Demo-pass-2026";
const JAZZ = "almaty-jazz-night-demo";

type Role = "anonymous" | "attendee" | "organizer" | "admin";
const EMAIL: Record<Exclude<Role, "anonymous">, string> = {
  attendee: "aliya@demo.biletflow.kz",
  organizer: "organizer@demo.biletflow.kz",
  admin: "admin@demo.biletflow.kz",
};

type Ids = { eventId: string; orderId: string; pendingOrderId: string; caseId: string };
type Route = {
  name: string;
  role: Role;
  path: (ids: Ids) => string;
  /** Extra checks, in English only (the text comes from messages/en.json). */
  check?: (page: Page) => Promise<void>;
};

const heading = (page: Page, name: string | RegExp) => page.getByRole("heading", { name }).first();

const ROUTES: Route[] = [
  {
    name: "home",
    role: "anonymous",
    path: () => "/",
    check: async (page) => {
      await expect(heading(page, en.home.title)).toBeVisible();
      await expect(page.getByRole("link", { name: en.home.browse })).toBeVisible();
      await expect(page.getByRole("link", { name: en.home.getStarted })).toBeVisible();
    },
  },
  {
    name: "events",
    role: "anonymous",
    path: () => "/events",
    check: async (page) => {
      await expect(heading(page, en.events.title)).toBeVisible();
      await expect(page.getByRole("searchbox", { name: en.events.search })).toBeVisible();
      await expect(page.getByRole("button", { name: en.events.searchButton })).toBeVisible();
      await expect(page.getByRole("link", { name: /Almaty Jazz Night/ }).first()).toBeVisible();
    },
  },
  {
    name: "event-detail",
    role: "anonymous",
    path: () => `/events/${JAZZ}`,
    check: async (page) => {
      await expect(heading(page, "Almaty Jazz Night")).toBeVisible();
      await expect(heading(page, en.event.view.tickets)).toBeVisible();
      await expect(page.getByRole("combobox", { name: /Quantity for Standard/ })).toBeVisible();
    },
  },
  {
    name: "login",
    role: "anonymous",
    path: () => "/login",
    check: async (page) => {
      await expect(heading(page, en.auth.login.title)).toBeVisible();
      await expect(page.getByLabel(en.auth.email)).toBeVisible();
      await expect(page.getByLabel(en.auth.password)).toBeVisible();
      await expect(page.getByRole("button", { name: en.auth.login.submit })).toBeVisible();
      await expect(page.getByRole("link", { name: en.auth.login.forgot })).toBeVisible();
    },
  },
  {
    name: "register",
    role: "anonymous",
    path: () => "/register",
    check: async (page) => {
      await expect(heading(page, en.auth.register.title)).toBeVisible();
      await expect(page.getByLabel(en.auth.fullName)).toBeVisible();
      await expect(page.getByLabel(en.auth.email)).toBeVisible();
      await expect(page.getByLabel(en.auth.password, { exact: true })).toBeVisible();
      await expect(page.getByLabel(en.auth.confirmPassword)).toBeVisible();
      await expect(page.getByRole("button", { name: en.auth.register.submit })).toBeVisible();
    },
  },
  {
    name: "forgot-password",
    role: "anonymous",
    path: () => "/forgot-password",
    check: async (page) => {
      await expect(heading(page, en.auth.forgot.title)).toBeVisible();
      await expect(page.getByLabel(en.auth.email)).toBeVisible();
      await expect(page.getByRole("button", { name: en.auth.forgot.submit })).toBeVisible();
    },
  },
  {
    name: "reset-password",
    role: "anonymous",
    path: () => "/reset-password?token=smoke",
    check: async (page) => {
      await expect(heading(page, en.auth.reset.title)).toBeVisible();
      await expect(page.getByRole("button", { name: en.auth.reset.submit })).toBeVisible();
    },
  },
  {
    name: "verify-email",
    role: "anonymous",
    path: () => "/verify-email",
    check: async (page) => {
      await expect(heading(page, en.auth.verify.title)).toBeVisible();
      await expect(page.getByRole("button", { name: en.auth.verify.resend })).toBeVisible();
    },
  },
  {
    name: "checkout",
    role: "attendee",
    path: (ids) => `/checkout/${ids.pendingOrderId}`,
    check: async (page) => {
      await expect(heading(page, en.checkout.title)).toBeVisible();
      await expect(page.getByText(en.common.demo, { exact: true }).first()).toBeVisible();
      await expect(page.getByRole("button", { name: /Pay .* \(DEMO: succeeds\)/ })).toBeVisible();
      await expect(page.getByRole("button", { name: en.checkout.payFail })).toBeVisible();
      await expect(page.getByRole("button", { name: en.checkout.abandon })).toBeVisible();
    },
  },
  {
    name: "order",
    role: "attendee",
    path: (ids) => `/orders/${ids.orderId}`,
    check: async (page) => {
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByRole("button", { name: /Download PDF: ticket / }).first()).toBeVisible();
      await expect(page.getByRole("link", { name: en.support.getHelp })).toBeVisible();
    },
  },
  {
    name: "my-orders",
    role: "attendee",
    path: () => "/orders",
    check: async (page) => {
      await expect(heading(page, en.orders.title)).toBeVisible();
      await expect(page.getByRole("link", { name: new RegExp(en.orders.view) }).first()).toBeVisible();
    },
  },
  {
    name: "my-tickets",
    role: "attendee",
    path: () => "/tickets",
    check: async (page) => {
      await expect(heading(page, en.tickets.title)).toBeVisible();
      await expect(page.getByRole("img", { name: /QR code for ticket/ }).first()).toBeVisible();
      await expect(page.getByRole("button", { name: /Download PDF: ticket / }).first()).toBeVisible();
    },
  },
  {
    name: "notifications",
    role: "attendee",
    path: () => "/notifications",
    check: async (page) => {
      await expect(heading(page, en.notifications.title)).toBeVisible();
    },
  },
  {
    name: "support-list",
    role: "attendee",
    path: () => "/support",
    check: async (page) => {
      await expect(heading(page, en.support.title)).toBeVisible();
      await expect(page.getByRole("link", { name: /Second ticket for my friend/ })).toBeVisible();
    },
  },
  {
    name: "support-new",
    role: "attendee",
    path: () => "/support/new",
    check: async (page) => {
      await expect(heading(page, en.support.form.title)).toBeVisible();
      await expect(page.getByLabel(en.support.category.label)).toBeVisible();
      await expect(page.getByLabel(en.support.form.subject)).toBeVisible();
      await expect(page.getByLabel(en.support.form.message)).toBeVisible();
      await expect(page.getByRole("button", { name: en.support.form.submit })).toBeVisible();
    },
  },
  {
    name: "support-case",
    role: "attendee",
    path: (ids) => `/support/${ids.caseId}`,
    check: async (page) => {
      await expect(heading(page, /Second ticket for my friend/)).toBeVisible();
    },
  },
  {
    name: "organizer-events",
    role: "organizer",
    path: () => "/organizer/events",
    check: async (page) => {
      await expect(heading(page, en.organizer.events.title)).toBeVisible();
      await expect(page.getByRole("link", { name: en.organizer.events.new })).toBeVisible();
    },
  },
  {
    name: "organizer-new-event",
    role: "organizer",
    path: () => "/organizer/events/new",
    check: async (page) => {
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByRole("textbox").first()).toBeVisible();
    },
  },
  {
    name: "organizer-profile",
    role: "organizer",
    path: () => "/organizer/profile",
    check: async (page) => {
      await expect(heading(page, en.organizer.profile.title)).toBeVisible();
      await expect(page.getByLabel(en.organizer.profile.displayName)).toBeVisible();
      await expect(page.getByLabel(en.organizer.profile.contactEmail)).toBeVisible();
      await expect(heading(page, en.organizer.payout.title)).toBeVisible();
    },
  },
  {
    name: "organizer-analytics",
    role: "organizer",
    path: () => "/organizer/analytics",
    check: async (page) => {
      await expect(heading(page, en.analytics.title)).toBeVisible();
      await expect(page.getByText(en.analytics.kpi.sold).first()).toBeVisible();
    },
  },
  ...(
    [
      ["details", ""],
      ["tickets", "/tickets"],
      ["activation", "/activation"],
      ["staff", "/staff"],
      ["preview", "/preview"],
      ["campaigns", "/campaigns"],
      ["attendees", "/attendees"],
      ["orders", "/orders"],
      ["analytics", "/analytics"],
      ["history", "/history"],
    ] as const
  ).map(
    ([tab, suffix]): Route => ({
      name: `organizer-event-${tab}`,
      role: "organizer",
      path: (ids) => `/organizer/events/${ids.eventId}${suffix}`,
      check: async (page) => {
        await expect(heading(page, "Almaty Jazz Night")).toBeVisible();
        const nav = page.getByRole("navigation", { name: "Almaty Jazz Night" });
        await expect(nav.getByRole("link", { name: en.organizer.manage.tabs[tab] })).toBeVisible();
      },
    }),
  ),
  {
    name: "admin",
    role: "admin",
    path: () => "/admin",
    check: async (page) => {
      await expect(heading(page, en.admin.title)).toBeVisible();
      for (const tab of ["overview", "users", "events", "reports"] as const) {
        const nav = page.getByRole("navigation", { name: en.admin.title });
        await expect(nav.getByText(en.admin.tabs[tab], { exact: true })).toBeVisible();
      }
    },
  },
];

const SIZES = [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 390, height: 844 },
] as const;
const LOCALES = ["en", "kk", "ru"] as const;

async function token(request: APIRequestContext, email: string): Promise<string> {
  const response = await request.post(`${API}/api/v1/auth/login`, {
    data: { email, password: PASSWORD },
    headers: { "X-Client": "scanner" },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).access_token as string;
}

async function signedInPage(browser: Browser, role: Role): Promise<Page> {
  const page = await browser.newPage();
  if (role === "anonymous") return page;
  await page.goto("/en/login");
  await page.getByLabel(en.auth.email).fill(EMAIL[role]);
  await page.getByLabel(en.auth.password).fill(PASSWORD);
  await page.getByRole("button", { name: en.auth.login.submit }).click();
  await expect(page).not.toHaveURL(/\/login/);
  return page;
}

/** Wait for client data to load: no "Loading…" text in any locale is left on the page. */
async function settled(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.getByText(/^(Loading…|Жүктелуде…|Загрузка…)$/)).toHaveCount(0);
}

test.describe.configure({ mode: "serial" });

let ids: Ids;
let attendeeToken: string;

test.beforeAll(async ({ request }) => {
  const organizer = { Authorization: `Bearer ${await token(request, EMAIL.organizer)}` };
  attendeeToken = await token(request, EMAIL.attendee);
  const attendee = { Authorization: `Bearer ${attendeeToken}` };
  const events = (await (await request.get(`${API}/api/v1/organizer/events`, { headers: organizer })).json()) as {
    id: string;
    slug: string;
  }[];
  const jazz = events.find((e) => e.slug === JAZZ)!;
  const orders = (await (await request.get(`${API}/api/v1/me/orders`, { headers: attendee })).json()) as {
    id: string;
    status: string;
  }[];
  const cases = (await (await request.get(`${API}/api/v1/support/cases`, { headers: attendee })).json()) as {
    id: string;
  }[];
  // A pending order to show the DEMO payment page; it is abandoned again in afterAll.
  const event = await (await request.get(`${API}/api/v1/events/${JAZZ}`)).json();
  const standard = event.ticket_types.find((tt: { name: string }) => tt.name === "Standard");
  const pending = await request.post(`${API}/api/v1/orders`, {
    headers: attendee,
    data: { event_id: event.id, items: [{ ticket_type_id: standard.id, quantity: 1 }] },
  });
  expect(pending.ok(), await pending.text()).toBeTruthy();
  ids = {
    eventId: jazz.id,
    orderId: orders.find((o) => o.status === "confirmed")!.id,
    pendingOrderId: (await pending.json()).id,
    caseId: cases[0].id,
  };
});

test.afterAll(async ({ request }) => {
  if (!ids?.pendingOrderId) return;
  await request.post(`${API}/api/v1/orders/${ids.pendingOrderId}/abandon`, {
    headers: { Authorization: `Bearer ${attendeeToken}` },
  });
});

for (const role of ["anonymous", "attendee", "organizer", "admin"] as const) {
  test(`smoke: ${role} routes`, async ({ browser }) => {
    test.setTimeout(600_000);
    const page = await signedInPage(browser, role);
    for (const route of ROUTES.filter((r) => r.role === role)) {
      for (const locale of LOCALES) {
        for (const size of SIZES) {
          await test.step(`${route.name} ${locale} ${size.name}`, async () => {
            await page.setViewportSize({ width: size.width, height: size.height });
            await page.goto(`/${locale}${route.path(ids)}`);
            await settled(page);
            await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
            if (locale === "en") await route.check?.(page);
            // Nothing pushes the page sideways (long kk/ru words included).
            const overflow = await page.evaluate(
              () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
            );
            expect.soft(overflow, `${route.name} ${locale} ${size.name} overflows by ${overflow}px`).toBeLessThanOrEqual(0);
            if (SHOTS_DIR) {
              await page.screenshot({
                path: `${SHOTS_DIR}/${route.name}.${locale}.${size.name}.png`,
                fullPage: true,
                animations: "disabled",
              });
            }
          });
        }
      }
    }
    await page.close();
  });
}

test("register: the header's Create account link shows a fresh form after signing up", async ({ page }) => {
  await page.goto("/en/register");
  await page.getByLabel(en.auth.fullName).fill("Smoke Register");
  await page.getByLabel(en.auth.email).fill(`smoke-register-${Date.now()}@example.com`);
  await page.getByLabel(en.auth.password, { exact: true }).fill(PASSWORD);
  await page.getByLabel(en.auth.confirmPassword).fill(PASSWORD);
  await page.getByRole("button", { name: en.auth.register.submit }).click();
  await expect(heading(page, en.auth.register.doneTitle)).toBeVisible();

  await page.getByRole("link", { name: en.nav.register }).click();
  await expect(heading(page, en.auth.register.title)).toBeVisible();
  await expect(page.getByRole("button", { name: en.auth.register.submit })).toBeVisible();
});

test("register: passwords must match, and Show password reveals both", async ({ page }) => {
  await page.goto("/en/register");
  const password = page.getByLabel(en.auth.password, { exact: true });
  const confirm = page.getByLabel(en.auth.confirmPassword);
  await expect(password).toHaveAttribute("type", "password");
  await page.getByLabel(en.auth.showPassword).check();
  await expect(password).toHaveAttribute("type", "text");
  await expect(confirm).toHaveAttribute("type", "text");

  await page.getByLabel(en.auth.fullName).fill("Smoke Mismatch");
  await page.getByLabel(en.auth.email).fill(`smoke-mismatch-${Date.now()}@example.com`);
  await password.fill(PASSWORD);
  await confirm.fill(`${PASSWORD}-typo`);
  await page.getByRole("button", { name: en.auth.register.submit }).click();
  await expect(page.getByText(en.auth.passwordMismatch)).toBeVisible();
  await expect(heading(page, en.auth.register.title)).toBeVisible();
});

test("login: an unconfirmed account can't sign in and can ask for a new link", async ({ page, request }) => {
  const email = `smoke-unconfirmed-${Date.now()}@example.com`;
  const created = await request.post(`${API}/api/v1/auth/register`, {
    data: { email, password: PASSWORD, full_name: "Smoke Unconfirmed", role: "attendee", locale: "en" },
  });
  expect(created.status()).toBe(202);

  await page.goto("/en/login");
  await page.getByLabel(en.auth.email).fill(email);
  await page.getByLabel(en.auth.password).fill(PASSWORD);
  await page.getByRole("button", { name: en.auth.login.submit }).click();
  await expect(page.getByText(en.errors.email_not_confirmed)).toBeVisible();
  await page.getByRole("button", { name: en.auth.verify.resend }).click();
  await expect(page.getByText(en.auth.verify.resent)).toBeVisible();
});
