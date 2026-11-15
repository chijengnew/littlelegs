import { expect, test, type Page } from "@playwright/test";
import { E2E_API, mockApi } from "./mockApi";
import { nextStep, searchCandidates } from "./conditions";

const NOW = new Date("2026-11-15T12:00:00+08:00");

function failCandidates(page: Page, status: number, body: Record<string, unknown>) {
  return page.route(`${E2E_API}/v1/trips/candidates`, (route) =>
    route.fulfill({
      status,
      contentType: "application/problem+json",
      body: JSON.stringify({ title: "Error", status, trace_id: "0190a000-0000-7000-8000-00000000abcd", ...body }),
    }),
  );
}

test("出發時間已過：上方不出現橫幅，只在出發時間欄位下方提示", async ({ page }) => {
  await mockApi(page);
  await failCandidates(page, 409, { code: "DEPARTURE_PASSED", detail: "後端原文" });
  await page.goto("/planner");
  await searchCandidates(page);
  await expect(page.locator("#err-depart_time")).toHaveText("出發時間已過，請選擇之後的時間");
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  await expect(page.getByText("出發時間已過，請選擇新的時間")).toHaveCount(0);
});

test("欄位格式不正確：上方橫幅只有說明，不顯示錯誤追蹤編號", async ({ page }) => {
  await mockApi(page);
  await failCandidates(page, 422, {
    code: "VALIDATION_FAILED",
    detail: "輸入欄位不合法",
    errors: [{ loc: ["body", "conditions", "depart_time"], msg: "Value error, 時間必須是 15 分鐘刻度", type: "value_error" }],
  });
  await page.goto("/planner");
  await searchCandidates(page);
  await expect(page.getByRole("main").getByRole("alert")).toHaveText("!有欄位格式不正確，請檢查後再送出。");
  await expect(page.getByText(/錯誤追蹤編號|0190a000-0000-7000-8000-00000000abcd|Value error/)).toHaveCount(0);
  await expect(page.locator("#err-depart_time")).toHaveText("請檢查這個欄位");
});

test("桌機：上方錯誤橫幅與條件表單同寬", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockApi(page);
  await failCandidates(page, 422, { code: "VALIDATION_FAILED", detail: "輸入欄位不合法", errors: [] });
  await page.goto("/planner");
  await searchCandidates(page);
  const banner = await page.getByRole("main").getByRole("alert").boundingBox();
  const card = await page.locator("section[aria-labelledby='cond-step-title']").boundingBox();
  expect(Math.abs(banner!.x - card!.x)).toBeLessThanOrEqual(1);
  expect(Math.abs(banner!.width - card!.width)).toBeLessThanOrEqual(1);
});

test("時間錯誤各自顯示在對應欄位下方", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.clock.setFixedTime(NOW);
  await mockApi(page);
  await page.goto("/planner");
  await page.locator("#f-date").fill("2026-11-15");
  await page.locator("#f-depart").selectOption("09:00");
  await page.locator("#f-return").selectOption("10:30");
  await nextStep(page);
  const depart = await page.locator("#f-depart").boundingBox();
  const ret = await page.locator("#f-return").boundingBox();
  const departErr = await page.locator("#err-depart_time").boundingBox();
  const returnErr = await page.locator("#err-return_time").boundingBox();
  expect(Math.abs(departErr!.x - depart!.x)).toBeLessThanOrEqual(1);
  expect(Math.abs(returnErr!.x - ret!.x)).toBeLessThanOrEqual(1);
  expect(departErr!.y).toBeGreaterThan(depart!.y + depart!.height - 1);
  expect(returnErr!.y).toBeGreaterThan(ret!.y + ret!.height - 1);
  await expect(page.locator("#f-return")).toHaveAttribute("aria-describedby", "err-return_time");
});

test("其他地點：建議次數用完的提示緊接在搜尋框下方", async ({ page }) => {
  await mockApi(page);
  await page.route(`${E2E_API}/v1/endpoints/autocomplete`, (route) =>
    route.fulfill({
      status: 429,
      contentType: "application/problem+json",
      body: JSON.stringify({ title: "Too Many Requests", status: 429, code: "AUTOCOMPLETE_LIMIT", limit_window: "session" }),
    }),
  );
  await page.goto("/planner");
  await nextStep(page);
  const start = page.getByRole("group", { name: "起點" });
  await start.getByRole("tab", { name: "其他地點" }).click();
  const search = start.getByPlaceholder("輸入地址或地點名稱");
  await search.fill("台北車站");
  const message = start.getByText("請從清單中選一個地點，或清除後重新輸入");
  await expect(message).toBeVisible();
  const box = await search.boundingBox();
  const msg = await message.boundingBox();
  const name = await start.getByText("幫這個地點取個名字").boundingBox();
  expect(msg!.y).toBeGreaterThan(box!.y + box!.height - 1);
  expect(msg!.y + msg!.height).toBeLessThan(name!.y);
  await expect(search).toHaveAttribute("aria-invalid", "true");
});

for (const width of [320, 360, 375, 414]) {
  test(`寬度 ${width}px：步驟列每個步驟都只有一行`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await mockApi(page);
    await page.goto("/planner");
    const steps = page.getByRole("list", { name: "查詢步驟" }).getByRole("listitem");
    await expect(steps).toHaveCount(3);
    for (const item of await steps.all()) {
      const fits = await item.evaluate((el) => el.scrollWidth <= el.clientWidth && el.getBoundingClientRect().height <= 44);
      expect(fits).toBe(true);
    }
  });
}
