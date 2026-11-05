import { expect, test, type Page } from "@playwright/test";
import { CENTER, MUSEUM, START, mockApi } from "./mockApi";

const DELAY = { delayMs: 600 };

type Seen = { conditions: boolean; candidates: boolean; blankStay: boolean };

async function watchScreens(page: Page) {
  await page.addInitScript(() => {
    const seen = { conditions: false, candidates: false, blankStay: false };
    (window as unknown as { __seen: typeof seen }).__seen = seen;
    new MutationObserver(() => {
      if (document.querySelector("#f-date")) seen.conditions = true;
      if ([...document.querySelectorAll("h2")].some((h) => h.textContent === "候選景點")) seen.candidates = true;
      if ([...document.querySelectorAll("option")].some((o) => o.textContent === "—")) seen.blankStay = true;
    }).observe(document, { childList: true, subtree: true });
  });
}

const seen = (page: Page) => page.evaluate(() => (window as unknown as { __seen: Seen }).__seen);

async function searchAndPick(page: Page, picks: string[]) {
  await page.goto("/");
  await page.getByRole("group", { name: "起點" }).getByRole("searchbox").fill("測試");
  await page.getByRole("button", { name: new RegExp(START.name) }).click();
  await page.getByLabel("第 1 位孩子年齡").selectOption("4");
  await page.getByLabel("終點同起點").check();
  await page.getByRole("button", { name: "搜尋候選景點" }).click();
  for (const name of picks) await page.getByRole("checkbox", { name: `選擇${name}` }).check();
}

test("在選擇景點重新整理：直接停在原步驟、重查後勾選保留且同一 query_id，不會先閃設定條件", async ({ page }) => {
  const api = await mockApi(page, DELAY);
  await watchScreens(page);
  await searchAndPick(page, [MUSEUM.name]);
  await page.reload();
  await expect(page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` })).toBeChecked();
  expect((await seen(page)).conditions).toBe(false);
  await expect(page.getByText("正在回到剛才的畫面")).not.toBeVisible();
  const searches = api.called("/v1/trips/candidates");
  expect(searches).toHaveLength(2);
  expect(searches[1].body?.query_id).toBe(searches[0].body?.query_id);
  expect(api.called("/v1/trips/sort")).toHaveLength(0);
  expect(api.unexpected).toEqual([]);
});

test("在安排行程重新整理（沒有未檢查的調整）：一直停在行程頁，依上次方式重算", async ({ page }) => {
  const api = await mockApi(page, DELAY);
  await watchScreens(page);
  await searchAndPick(page, [MUSEUM.name, CENTER.name]);
  await page.getByRole("button", { name: "自動排出行程" }).click();
  await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible();
  expect(await seen(page)).toEqual({ conditions: false, candidates: false, blankStay: false });
  expect(api.called("/v1/trips/candidates")).toHaveLength(2);
  expect(api.called("/v1/trips/sort")).toHaveLength(2);
  expect(api.called("/v1/trips/check")).toHaveLength(0);
  expect(api.unexpected).toEqual([]);
});

test("在安排行程重新整理（有未檢查的調整）：停在行程頁並保留調整，不自動重算", async ({ page }) => {
  const api = await mockApi(page, DELAY);
  await watchScreens(page);
  await searchAndPick(page, [MUSEUM.name, CENTER.name]);
  await page.getByRole("button", { name: "自動排出行程" }).click();
  await page.getByLabel(`${MUSEUM.name}停留時間（分鐘）`).selectOption("120");
  await expect(page.getByText("你已調整順序或停留時間")).toBeVisible();
  const requeried = page.waitForResponse((r) => r.url().endsWith("/v1/trips/candidates"));
  await page.reload();
  await expect(page.getByText("你已調整順序或停留時間")).toBeVisible();
  await expect(page.getByLabel(`${MUSEUM.name}停留時間（分鐘）`)).toHaveValue("120");
  await expect(page.getByLabel(`${CENTER.name}停留時間（分鐘）`)).toHaveValue(String(CENTER.default_stay.minutes));
  await requeried;
  await expect(page.getByLabel(`${CENTER.name}停留時間（分鐘）`)).toHaveValue(String(CENTER.default_stay.minutes));
  await expect(page.getByRole("heading", { name: "時間軸" })).toHaveCount(0);
  expect(await seen(page)).toEqual({ conditions: false, candidates: false, blankStay: false });
  await page.getByRole("button", { name: "回到候選" }).click();
  await expect(page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` })).toBeChecked();
  expect(api.called("/v1/trips/sort")).toHaveLength(1);
  expect(api.called("/v1/trips/check")).toHaveLength(0);
  expect(api.unexpected).toEqual([]);
});
