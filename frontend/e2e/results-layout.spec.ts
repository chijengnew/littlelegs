import { expect, test, type Page } from "@playwright/test";
import { CENTER, E2E_API, MUSEUM, candidateResponse, mockApi } from "./mockApi";
import { searchCandidates } from "./conditions";

const noHorizontalScroll = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);

test("候選頁桌機：訪客沒有地圖欄也沒有登入提示；旅宿在右欄；底部列直接列出已選名稱，按 × 移除", async ({ page }) => {
  const api = await mockApi(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/planner");
  await searchCandidates(page);

  await expect(page.getByText(/後可以在地圖上看景點位置/)).toHaveCount(0);
  await expect(page.getByRole("region", { name: "登入後可查看地圖" })).toHaveCount(0);
  const list = await page.getByRole("region", { name: "候選景點清單" }).boundingBox();
  const lodging = await page.getByRole("heading", { name: "終點附近旅宿" }).boundingBox();
  expect(lodging!.x).toBeGreaterThanOrEqual(list!.x + list!.width);
  await expect(page.getByRole("group", { name: "切換列表或地圖" })).toHaveCount(0);

  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();
  await page.getByRole("checkbox", { name: `選擇${CENTER.name}` }).check();
  await expect(page.getByText("已選 2／5")).toBeVisible();
  const chips = page.getByRole("list", { name: "已選景點" });
  await expect(chips.getByText(MUSEUM.name)).toBeVisible();
  await expect(page.getByRole("button", { name: "查看" })).toBeHidden();

  await chips.getByRole("button", { name: `取消選擇${MUSEUM.name}` }).click();
  await expect(chips.getByText(MUSEUM.name)).toHaveCount(0);
  await expect(chips.getByRole("button", { name: `取消選擇${CENTER.name}` })).toBeFocused();
  await expect(page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` })).not.toBeChecked();
  await expect(page.getByRole("checkbox", { name: `選擇${CENTER.name}` })).toBeChecked();
  expect(await noHorizontalScroll(page)).toBe(true);
  expect(api.called("/v1/trips/sort")).toHaveLength(0);
  expect(api.unexpected).toEqual([]);
});

test("手機：訪客候選頁只有列表；行程頁沒有地圖切換，只顯示一行登入提示；訪客全程不載入 Google 地圖", async ({ page }) => {
  const api = await mockApi(page);
  const mapRequests: string[] = [];
  await page.route("https://maps.googleapis.com/**", (route) => {
    mapRequests.push(route.request().url());
    return route.abort();
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/planner");
  await searchCandidates(page);

  await expect(page.getByRole("group", { name: "切換列表或地圖" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "候選景點清單" })).toBeVisible();
  await expect(page.getByText("登入後可以在地圖上看路線")).toHaveCount(0);

  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();
  await expect(page.getByRole("button", { name: "自動排出行程" })).toBeInViewport();
  await page.getByRole("button", { name: "自動排出行程" }).click();

  await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "時間軸" })).toBeInViewport();
  await expect(page.getByRole("group", { name: "切換時間軸或地圖" })).toHaveCount(0);
  await expect(page.getByText("登入後可以在地圖上看路線")).toBeVisible();

  expect(mapRequests).toEqual([]);
  expect(api.unexpected).toEqual([]);
});

test("調整停留時間後：出現「有調整，尚未檢查」，時間軸與導航隱藏，且不自動呼叫檢查", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/planner");
  await searchCandidates(page);
  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();
  await page.getByRole("button", { name: "自動排出行程" }).click();
  await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible();

  await page.getByRole("button", { name: "調整順序與時間" }).click();
  await page.getByLabel(`${MUSEUM.name}停留時間（分鐘）`).selectOption("120");
  await expect(page.getByText("有調整，尚未檢查")).toBeVisible();
  await expect(page.getByRole("heading", { name: "時間軸" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "導航" })).toHaveCount(0);
  expect(api.called("/v1/trips/check")).toHaveLength(0);
});

for (const width of [320, 375, 768, 1024]) {
  test(`寬度 ${width}px：候選頁與行程頁沒有水平捲動`, async ({ page }) => {
    await mockApi(page);
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/planner");
    await searchCandidates(page);
    await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();
    expect(await noHorizontalScroll(page)).toBe(true);
    await page.getByRole("button", { name: "自動排出行程" }).click();
    await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible();
    expect(await noHorizontalScroll(page)).toBe(true);
    await page.getByRole("button", { name: "調整順序與時間" }).click();
    await expect(page.getByRole("button", { name: "完成" })).toBeVisible();
    expect(await noHorizontalScroll(page)).toBe(true);
  });
}

test("平板 1024：單欄，訪客沒有地圖也沒有列表／地圖切換，旅宿在候選之後", async ({ page }) => {
  await mockApi(page);
  await page.setViewportSize({ width: 1024, height: 800 });
  await page.goto("/planner");
  await searchCandidates(page);

  const list = await page.getByRole("region", { name: "候選景點清單" }).boundingBox();
  const lodging = await page.getByRole("heading", { name: "終點附近旅宿" }).boundingBox();
  expect(list!.width).toBeGreaterThanOrEqual(600);
  expect(lodging!.y).toBeGreaterThan(list!.y + list!.height);
  await expect(page.getByRole("group", { name: "切換列表或地圖" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "登入後可查看地圖" })).toHaveCount(0);
});

test("手機：沒有旅宿時直接顯示說明，不出現展開按鈕", async ({ page }) => {
  await mockApi(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/planner");
  await searchCandidates(page);
  await expect(page.getByText("附近沒有可列出的旅宿")).toBeVisible();
  await expect(page.getByRole("button", { name: /^展開/ })).toHaveCount(0);
});

test("手機：旅宿在候選之後，全部直接列出；設施用文字列出，不另外標示「有親子設施資訊」", async ({ page }) => {
  await mockApi(page);
  await page.route(`${E2E_API}/v1/trips/candidates`, async (route) => {
    const body = JSON.parse(route.request().postData() ?? "{}") as { query_id: string };
    const base = candidateResponse(body.query_id);
    const hotel = (n: number, name: string, distance_m: number) => ({
      place_id: `0190a000-0000-7000-8000-0000000000a${n}`, name, address: null, distance_m, distance_note: "終點直線距離",
      family_facilities: n === 4 ? [] : ["crib"], label: n === 4 ? "親子設施未確認" : "有親子設施資訊",
    });
    const lodging = {
      empty: false,
      note: null,
      items: [hotel(1, "測試旅館", 800), hotel(2, "測試民宿", 1500), hotel(3, "測試飯店", 2100), hotel(4, "測試會館", 2600)],
    };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...base, lodging }) });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/planner");
  await searchCandidates(page);

  const list = await page.getByRole("region", { name: "候選景點清單" }).boundingBox();
  const heading = await page.getByRole("heading", { name: "終點附近旅宿" }).boundingBox();
  expect(heading!.y).toBeGreaterThan(list!.y + list!.height);
  await expect(page.getByText("先看親子設施，再看距離")).toBeVisible();
  await expect(page.getByText("直線 0.8 km")).toBeVisible();
  await expect(page.getByText("嬰兒床").first()).toBeVisible();
  await expect(page.getByText("有親子設施資訊")).toHaveCount(0);
  await expect(page.getByText("測試會館")).toBeVisible();
  await expect(page.getByText("親子設施未確認")).toBeVisible();
  await expect(page.getByRole("button", { name: /顯示全部|收合/ })).toHaveCount(0);
});

test("行程頁：調整模式中上移／下移後焦點留在同一景點並播報新順序；有調整後才出現主要的「檢查這個行程」，取消會還原", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/planner");
  await searchCandidates(page);
  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();
  await page.getByRole("checkbox", { name: `選擇${CENTER.name}` }).check();
  await page.getByRole("button", { name: "自動排出行程" }).click();
  await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible();

  const check = page.getByRole("button", { name: "檢查這個行程" });
  await expect(check).toHaveCount(0);
  await page.getByRole("button", { name: "調整順序與時間" }).click();
  const editor = page.getByRole("region", { name: "調整順序與時間" });
  await expect(editor.getByRole("button", { name: "完成" })).toBeVisible();
  await expect(check).toHaveCount(0);

  const first = (await editor.locator("li strong").first().textContent())!;
  await editor.getByRole("button", { name: `將${first}往後移` }).click();
  await expect(editor.getByRole("button", { name: `將${first}往前移` })).toBeFocused();
  await expect(page.getByRole("status").filter({ hasText: `${first} 已移到第 2 個` })).toBeAttached();
  await expect(editor.locator("li strong").nth(1)).toHaveText(first);
  await expect(editor.getByText("有調整，尚未檢查")).toBeVisible();
  await expect.poll(() => check.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgb(32, 33, 36)");
  expect(api.called("/v1/trips/check")).toHaveLength(0);

  await editor.getByRole("button", { name: "取消" }).click();
  await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible();
  await page.getByRole("button", { name: "調整順序與時間" }).click();
  await expect(page.getByRole("region", { name: "調整順序與時間" }).locator("li strong").first()).toHaveText(first);
  expect(api.called("/v1/trips/check")).toHaveLength(0);
});
