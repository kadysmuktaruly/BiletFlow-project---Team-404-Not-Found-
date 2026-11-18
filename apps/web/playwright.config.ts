import { defineConfig, devices } from "@playwright/test";

// End-to-end tests against a running stack: the web app (E2E_BASE_URL, default
// http://localhost:3000) and the API (E2E_API_URL, default http://localhost:8000) with the
// demo seed loaded. Locally: `docker compose up -d`, then `npm run e2e -w @biletflow/web`.
// CI starts both itself (see .github/workflows/ci.yml, job "End-to-end").
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    locale: "en-US",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
