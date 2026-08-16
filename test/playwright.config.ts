import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.BASE_URL ?? "http://localhost:8000";

export default defineConfig({
  testDir: "./tests",
  // The suite shares one app container and therefore one SQLite database, so
  // cash and positions carry across files. Files run in order, one at a time.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Desktop-first terminal layout (PLAN.md §2); a wide viewport keeps
        // every panel on screen so nothing needs scrolling into view.
        viewport: { width: 1600, height: 950 },
      },
    },
  ],
});
