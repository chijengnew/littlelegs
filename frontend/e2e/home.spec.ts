import { expect, test } from "@playwright/test";
import { MUSEUM, mockApi } from "./mockApi";
import { searchCandidates } from "./conditions";

test("首頁：品牌標題與開始規劃入口，開啟首頁與進入規劃頁都不呼叫 API", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("帶孩子出門");
  await expect(page.getByText("示意畫面")).toBeVisible();
  await expect(page.getByText("一鍵開啟 Google 地圖導航")).toBeVisible();
  await expect(page.getByText("出遊準備清單，出門前逐項勾選")).toBeVisible();
  await page.getByRole("main").getByRole("link", { name: "開始規劃" }).first().click();
  await expect(page).toHaveURL(/\/planner$/);
  await expect(page.getByLabel("出遊日期")).toBeVisible();
  await expect(page.getByRole("banner").getByRole("link", { name: "開始規劃" })).toHaveCount(0);
  await expect(page).toHaveTitle("規劃行程｜LittleLegs");
  expect(api.calls).toEqual([]);
});

test("在首頁重新整理不會自動重查；回到規劃頁才重查，勾選仍在", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/planner");
  await searchCandidates(page);
  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();
  expect(api.called("/v1/trips/candidates")).toHaveLength(1);

  await page.getByRole("banner").getByRole("link", { name: "LittleLegs" }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("帶孩子出門");
  await page.waitForTimeout(800);
  expect(api.called("/v1/trips/candidates")).toHaveLength(1);

  await page.getByRole("banner").getByRole("link", { name: "繼續規劃" }).click();
  await expect(page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` })).toBeChecked();
  expect(api.called("/v1/trips/candidates")).toHaveLength(2);
  expect(api.unexpected).toEqual([]);
});
