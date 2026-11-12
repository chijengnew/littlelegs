import { expect, test, type Page } from "@playwright/test";
import { MUSEUM, mockApi } from "./mockApi";
import { searchCandidates } from "./conditions";

const noHorizontalScroll = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);

test("探險護照與任務徽章：訪客看玩法說明與示意，分頁切換，不呼叫會員 API", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/explore/passport");
  await expect(page.getByRole("heading", { level: 1, name: "小小探險家" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "探險護照與任務" });
  await expect(nav.getByRole("link", { name: "探險護照" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { level: 2, name: "到景點蓋章，收集探險護照" })).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "家長按「我要蓋章」，核對目前位置" })).toBeVisible();
  await expect(page.getByText("示意", { exact: true })).toBeVisible();
  await expect(page.getByText("會員功能尚未啟用。")).toBeVisible();
  await nav.getByRole("link", { name: "任務徽章" }).click();
  await expect(page).toHaveURL(/\/explore\/missions$/);
  await expect(nav.getByRole("link", { name: "任務徽章" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { level: 2, name: "到景點蓋章，收集探險護照" })).toBeVisible();
  expect(api.calls).toEqual([]);
});

test("探險護照頁在 320px 與桌機寬度都沒有水平捲動", async ({ page }) => {
  await mockApi(page);
  for (const width of [320, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/explore/passport");
    await expect(page.getByRole("heading", { level: 1, name: "小小探險家" })).toBeVisible();
    expect(await noHorizontalScroll(page), `${width}px`).toBe(true);
  }
});

test("地點詳情：訪客看到探險護照卡片與玩法連結，不查詢會員蓋章狀態", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto(`/places/${MUSEUM.place_id}`);
  const card = page.locator("#stamp");
  await expect(card.getByRole("heading", { level: 2, name: "探險護照" })).toBeVisible();
  await expect(card.getByText("登入會員後，到了這裡可以定位核對，蓋一枚印章收進探險護照。")).toBeVisible();
  await expect(card.getByRole("link", { name: "怎麼玩" })).toHaveAttribute("href", "/explore/passport");
  await expect(card.getByRole("button", { name: "我要蓋章" })).toHaveCount(0);
  const hero = await page.getByRole("heading", { level: 1, name: MUSEUM.name }).boundingBox();
  const facts = await page.getByRole("heading", { level: 2, name: "景點資訊" }).boundingBox();
  const box = await card.boundingBox();
  expect(box!.y).toBeGreaterThan(hero!.y);
  expect(box!.y).toBeLessThan(facts!.y);
  expect(api.calls.map((c) => c.path)).toEqual([`/v1/places/${MUSEUM.place_id}`]);
  expect(api.unexpected).toEqual([]);
});

test("行程時間軸的景點列有「蓋章」入口，樣式同導航小按鈕，連到地點詳情", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/planner");
  await searchCandidates(page);
  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();
  await page.getByRole("button", { name: "自動排出行程" }).click();
  await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible();
  const timeline = page.getByRole("region", { name: "時間軸" });
  const stamp = timeline.getByRole("link", { name: `到${MUSEUM.name}的地點詳情蓋章` });
  await expect(stamp).toHaveText("蓋章");
  await expect(stamp).toHaveAttribute("href", `/places/${MUSEUM.place_id}?from=plan#stamp`);
  const nav = timeline.getByRole("link", { name: /^使用 Google 地圖導航到/ }).first();
  for (const prop of ["border-radius", "font-size", "min-height"]) {
    expect(await stamp.evaluate((el, p) => getComputedStyle(el).getPropertyValue(p), prop)).toBe(
      await nav.evaluate((el, p) => getComputedStyle(el).getPropertyValue(p), prop),
    );
  }
  expect(api.unexpected).toEqual([]);
});

test("地點詳情的「返回」依來源連回原頁；來源不明時仍回規劃頁", async ({ page }) => {
  const api = await mockApi(page);
  const cases: [string, string, string][] = [
    ["passport", "/explore/passport", "返回"],
    ["history", "/account?tab=history", "返回"],
    ["favorites", "/account?tab=favorites", "返回"],
    ["plan", "/planner", "返回"],
    ["candidates", "/planner", "回到候選景點"],
    ["toString", "/planner", "返回"],
  ];
  for (const [from, href, name] of cases) {
    await page.goto(`/places/${MUSEUM.place_id}?from=${from}`);
    await expect(page.getByRole("heading", { level: 1, name: MUSEUM.name })).toBeVisible();
    await expect(page.getByRole("link", { name, exact: true })).toHaveAttribute("href", href);
  }
  expect(api.unexpected).toEqual([]);
});
