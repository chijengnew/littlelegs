import { defineConfig, devices } from "@playwright/test";
import { E2E_API, E2E_PORT } from "./e2e/mockApi";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${E2E_PORT}`,
    locale: "zh-TW",
    timezoneId: "Asia/Taipei",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npm run build && npm run start -- --port ${E2E_PORT}`,
    url: `http://localhost:${E2E_PORT}`,
    reuseExistingServer: false,
    timeout: 240_000,
    env: {
      NEXT_PUBLIC_API_BASE_URL: E2E_API,
      NEXT_PUBLIC_FIREBASE_API_KEY: "",
      NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN: "",
      NEXT_PUBLIC_FIREBASE_PROJECT_ID: "",
      NEXT_PUBLIC_FIREBASE_APP_ID: "",
      NEXT_PUBLIC_RECAPTCHA_ENTERPRISE_SITE_KEY: "",
      NEXT_PUBLIC_APP_CHECK_DEBUG: "false",
      NEXT_PUBLIC_GOOGLE_MAPS_API_KEY: "e2e-not-a-real-key",
      NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID: "DEMO_MAP_ID",
    },
  },
});
