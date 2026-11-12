import { expect, test, type Page } from "@playwright/test";
import type { components } from "../src/lib/api/schema";
import { CENTER, E2E_API, MUSEUM, candidateResponse, mockApi } from "./mockApi";
import { searchCandidates } from "./conditions";

type S = components["schemas"];
type Patch = (date: string) => Partial<S["CandidateResponse"]>;

async function withCandidates(page: Page, patch: Patch) {
  await page.route(`${E2E_API}/v1/trips/candidates`, async (route) => {
    const body = route.request().postDataJSON() as { query_id: string; conditions: { date: string } };
    const res = { ...candidateResponse(body.query_id), ...patch(body.conditions.date) };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(res) });
  });
}

const many = (n: number): S["CandidateOut"][] =>
  Array.from({ length: n }, (_, i) => ({
    ...MUSEUM,
    place_id: `0190a000-0000-7000-8000-0000000002${String(i).padStart(2, "0")}`,
    name: `測試景點${i + 1}`,
  }));

test("整張卡片都能點選，已選卡片顯示第幾個；地址只留縣市與區、推薦原因改成短標籤", async ({ page }) => {
  await mockApi(page);
  await withCandidates(page, () => ({
    candidates: [{ ...MUSEUM, address: "116臺北市文山區新光路二段30號", indoor: { value: "outdoor", confirmation: "inferred" } }],
  }));
  await page.goto("/planner");
  await searchCandidates(page);

  const card = page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: MUSEUM.name }) });
  await expect(card.getByText("臺北市文山區", { exact: true })).toBeVisible();
  await expect(page.getByText(/新光路/)).toHaveCount(0);
  await expect(card.getByText("室外", { exact: true })).toBeVisible();
  await expect(page.getByText(/推定/)).toHaveCount(0);
  await expect(card.getByText("離起點近")).toBeVisible();
  await expect(page.getByText(/距離起點較近/)).toHaveCount(0);
  await expect(page.getByText(/共 \d+ 個候選/)).toHaveCount(0);
  await expect(page.getByText(/營業時間會在排序或檢查行程時確認/)).toHaveCount(0);

  const box = page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` });
  await card.getByRole("heading", { name: MUSEUM.name }).click();
  await expect(box).toBeChecked();
  await expect(card.getByText("第 1 個")).toBeVisible();
  await card.getByText("臺北市文山區").click();
  await expect(box).not.toBeChecked();
});

test("選滿 5 個後，其他卡片顯示「已達上限」，點了會出現提示；移除一個後提示消失", async ({ page }) => {
  await mockApi(page);
  await withCandidates(page, () => ({ candidates: many(6), candidate_count: 6 }));
  await page.goto("/planner");
  await searchCandidates(page);

  for (let i = 1; i <= 5; i++) await page.getByRole("checkbox", { name: `選擇測試景點${i}` }).check();
  const sixth = page.getByRole("checkbox", { name: "選擇測試景點6" });
  await expect(sixth).toHaveAttribute("aria-disabled", "true");
  await expect(page.getByText("已達上限")).toBeVisible();

  const notice = page.locator("p[aria-hidden='true']", { hasText: "最多選 5 個景點，請先移除一個再選" });
  await expect(notice).toHaveCount(0);
  await page.getByRole("heading", { name: "測試景點6" }).click();
  await expect(sixth).not.toBeChecked();
  await expect(notice).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "最多選 5 個景點，請先移除一個再選" })).toHaveCount(1);

  await page.getByRole("checkbox", { name: "選擇測試景點1" }).uncheck();
  await expect(notice).toHaveCount(0);
  await page.getByRole("checkbox", { name: "選擇測試景點1" }).check();
  await sixth.click({ force: true });
  await expect(sixth).not.toBeChecked();
  await expect(notice).toBeVisible();

  await page.getByRole("checkbox", { name: "選擇測試景點1" }).uncheck();
  await expect(notice).toHaveCount(0);
  await expect(sixth).not.toHaveAttribute("aria-disabled", "true");
});

function routeWeather(date: string, rainFilter: boolean): S["WeatherOut"] {
  const next = new Date(`${date}T12:00:00+08:00`);
  next.setDate(next.getDate() + 1);
  const d2 = next.toISOString().slice(0, 10);
  const part = (label: string, a: string, b: string, percent: number) => ({ label, start: a, end: b, percent, type: "RAIN" });
  const day = (p: number) => part("日間", `${date}T07:00:00+08:00`, `${date}T19:00:00+08:00`, p);
  const night = (p: number) => part("夜間", `${date}T19:00:00+08:00`, `${d2}T07:00:00+08:00`, p);
  return {
    status: rainFilter ? "triggered" : "not_requested",
    max_precipitation_percent: 80,
    threshold_percent: 60,
    location: "start",
    note: null,
    explanation: "含其他降水，各區以日間／夜間預報判斷",
    source: "google",
    uncovered: [],
    parts: [day(30), night(70)],
    rain_filter: rainFilter,
    areas: [
      { label: "臺北市中正區", roles: ["start", "end"], status: "not_triggered", max_precipitation_percent: 30, parts: [day(30), night(70)], uncovered: [], note: null },
      { label: "新北市石碇區", roles: [], status: "triggered", max_precipitation_percent: 80, parts: [day(80)], uncovered: [], note: null },
    ],
  };
}

for (const rainFilter of [false, true]) {
  test(`沿途天氣：各區一行、景點卡片顯示所在區的降水機率（下雨只排室內：${rainFilter ? "有" : "沒"}勾）`, async ({ page }) => {
    await mockApi(page);
    await withCandidates(page, (date) => ({
      weather: routeWeather(date, rainFilter),
      candidates: [
        { ...MUSEUM, weather_area: 0 },
        { ...CENTER, weather_area: 1 },
      ],
    }));
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/planner");
    await searchCandidates(page);

    const weather = page.getByRole("region", { name: "沿途天氣" });
    const rows = weather.getByRole("listitem");
    await expect(rows).toHaveCount(2);
    await expect(rows.nth(0)).toContainText("臺北市中正區");
    await expect(rows.nth(0)).toContainText("起點");
    await expect(rows.nth(0)).toContainText("終點");
    await expect(rows.nth(0)).toContainText("30%");
    await expect(rows.nth(1)).toContainText("新北市石碇區");
    await expect(rows.nth(1)).toContainText("80%");

    const museum = page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: MUSEUM.name }) });
    const center = page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: CENTER.name }) });
    await expect(museum.getByText("降雨機率 30%")).toBeVisible();
    await expect(center.getByText("降雨機率 80%")).toBeVisible();
    await expect(page.getByText(/虛線是|未觸發室內限制|Source: Includes weather data/)).toHaveCount(0);

    if (rainFilter) {
      await expect(weather.getByText("降水機率達 60% 的區域只排室內景點")).toBeVisible();
      await expect(rows.nth(1).getByText("只排室內")).toBeVisible();
    } else {
      await expect(weather.getByText("只排室內")).toHaveCount(0);
    }

    const list = await page.getByRole("region", { name: "候選景點清單" }).boundingBox();
    const side = await weather.boundingBox();
    expect(side!.x).toBeGreaterThanOrEqual(list!.x + list!.width);
  });
}

test("手機：底部列只顯示已選數量與查看；面板可移除景點，關閉後焦點回到查看", async ({ page }) => {
  await mockApi(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/planner");
  await searchCandidates(page);

  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();
  await page.getByRole("checkbox", { name: `選擇${CENTER.name}` }).check();
  await expect(page.getByText("已選 2／5")).toBeVisible();
  await expect(page.getByRole("list", { name: "已選景點" })).toHaveCount(0);

  await page.getByRole("button", { name: "查看" }).click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByRole("heading", { name: "已選景點 2／5" })).toBeFocused();
  await sheet.getByRole("button", { name: `取消選擇${MUSEUM.name}` }).click();
  await expect(sheet.getByRole("heading", { name: "已選景點 1／5" })).toBeVisible();
  await expect(sheet.getByText(/旅宿不會加入停留景點/)).toHaveCount(0);
  await sheet.getByRole("button", { name: "關閉" }).click();
  await expect(sheet).toBeHidden();
  await expect(page.getByRole("button", { name: "查看" })).toBeFocused();
  await expect(page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` })).not.toBeChecked();
});

test("從首頁進入設定條件時有「回首頁」；從選擇景點頁按「修改條件」回來時沒有；再回首頁按開始規劃又會出現", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("link", { name: "開始規劃" }).first().click();
  await expect(page.getByRole("link", { name: "回首頁" })).toBeVisible();
  await searchCandidates(page);
  await page.getByRole("button", { name: "修改條件" }).click();
  await expect(page.getByRole("button", { name: "下一步" })).toBeVisible();
  await expect(page.getByRole("link", { name: "回首頁" })).toHaveCount(0);
  await page.getByRole("link", { name: "LittleLegs" }).first().click();
  await page.waitForURL("**/");
  await page.getByRole("link", { name: "開始規劃" }).first().click();
  await expect(page.getByRole("link", { name: "回首頁" })).toBeVisible();
});

test("桌機 1280×720：捲到底時，修改條件、沿途天氣與旅宿仍在畫面上", async ({ page }) => {
  await mockApi(page);
  await withCandidates(page, (date) => ({
    candidates: many(8).map((c) => ({ ...c, weather_area: 0 })),
    weather: routeWeather(date, false),
  }));
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/planner");
  await searchCandidates(page);
  await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
  await expect(page.getByRole("button", { name: "修改條件" })).toBeInViewport();
  await expect(page.getByRole("region", { name: "沿途天氣" })).toBeInViewport();
  await expect(page.getByRole("heading", { name: "終點附近旅宿" })).toBeInViewport();
});


test("地點詳情在同一分頁開啟；「回到候選景點」回到原本的清單，已選景點保留且不重新查詢", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/planner");
  await searchCandidates(page);
  await expect(page.getByRole("button", { name: "修改條件" })).toHaveCSS("background-color", "rgb(237, 245, 238)");
  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();

  const card = page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: MUSEUM.name }) });
  const detail = card.getByRole("link", { name: "地點詳情" });
  await expect(detail).not.toHaveAttribute("target", "_blank");
  await expect(detail).toHaveCSS("text-decoration-line", "none");
  await detail.click();
  await expect(page).toHaveURL(new RegExp(`/places/${MUSEUM.place_id}\\?from=candidates$`));
  await expect(page.getByRole("heading", { level: 1, name: MUSEUM.name })).toBeVisible();
  await expect(page.getByRole("link", { name: "返回", exact: true })).toHaveCount(0);

  await page.getByRole("link", { name: "回到候選景點" }).click();
  await expect(page).toHaveURL(/\/planner$/);
  await expect(page.getByRole("heading", { name: "挑幾個想去的地方" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` })).toBeChecked();
  expect(api.called("/v1/trips/candidates")).toHaveLength(1);

  await page.goto(`/places/${MUSEUM.place_id}?from=candidates`);
  await expect(page.getByRole("link", { name: "回到候選景點" })).toHaveAttribute("href", "/planner");
  expect(api.unexpected).toEqual([]);
});
