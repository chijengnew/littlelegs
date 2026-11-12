import { expect, test, type Page } from "@playwright/test";
import { E2E_API, candidateResponse, mockApi } from "./mockApi";
import { searchCandidates } from "./conditions";

const noHorizontalScroll = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);

test("不存在的網址：404 狀態頁，有回到首頁與開始規劃，不呼叫 API", async ({ page }) => {
  const api = await mockApi(page);
  const response = await page.goto("/no-such-page");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { level: 1, name: "找不到這個頁面" })).toBeVisible();
  await expect(page.getByRole("main").getByRole("link", { name: "回到首頁" })).toHaveAttribute("href", "/");
  await expect(page.getByRole("main").getByRole("link", { name: "開始規劃" })).toHaveAttribute("href", "/planner");
  await expect(page.getByRole("banner")).toBeVisible();
  expect(api.calls).toEqual([]);
});

test("地點不存在：顯示狀態卡與回到規劃，不是整頁錯誤", async ({ page }) => {
  await mockApi(page);
  const missing = "0190a000-0000-7000-8000-0000000000ff";
  await page.route(`${E2E_API}/v1/places/${missing}`, (route) =>
    route.fulfill({
      status: 404,
      contentType: "application/problem+json",
      body: JSON.stringify({ type: "about:blank", title: "Not Found", status: 404, code: "NOT_FOUND", detail: "not found" }),
    }),
  );
  await page.goto(`/places/${missing}`);
  await expect(page.getByRole("heading", { name: "找不到這個地點" })).toBeVisible();
  await expect(page.getByRole("main").getByRole("link", { name: "回到規劃" })).toHaveAttribute("href", "/planner");
  await expect(page.getByRole("banner")).toBeVisible();
});

test("沒有候選景點：空白狀態提供修改條件，按下後回到設定條件第 1 步", async ({ page }) => {
  await mockApi(page);
  await page.route(`${E2E_API}/v1/trips/candidates`, async (route) => {
    const body = JSON.parse(route.request().postData() ?? "{}") as { query_id: string };
    const empty = { ...candidateResponse(body.query_id), candidates: [], candidate_count: 0, operation: "no_results" as const };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(empty) });
  });
  await page.goto("/planner");
  await searchCandidates(page);
  await expect(page.getByRole("heading", { name: "附近 30 公里內沒有符合條件的候選景點" })).toBeVisible();
  await expect(page.getByRole("button", { name: "自動排出行程" })).toBeDisabled();
  await page.getByRole("region", { name: "候選景點清單" }).getByRole("button", { name: "修改條件" }).click();
  await expect(page.getByRole("heading", { name: "什麼時候出發？" })).toBeVisible();
});

for (const width of [320, 1440]) {
  test(`寬度 ${width}px：首頁、條件、狀態頁沒有水平捲動`, async ({ page }) => {
    await mockApi(page);
    await page.setViewportSize({ width, height: 800 });
    for (const path of ["/", "/planner", "/no-such-page", "/account/deleted", "/forgot-password", "/verify-email"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeAttached();
      expect(await noHorizontalScroll(page), path).toBe(true);
    }
  });
}
