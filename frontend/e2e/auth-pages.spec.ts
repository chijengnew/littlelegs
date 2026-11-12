import { expect, test } from "@playwright/test";
import { MUSEUM, mockApi } from "./mockApi";
import { searchCandidates } from "./conditions";

test("中途去登入頁再回來：候選與已選景點仍在，不重新查詢", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/planner");
  await searchCandidates(page);
  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();

  await page.getByRole("banner").getByRole("button", { name: "帳號選單（未登入）", exact: true }).click();
  await page.getByRole("banner").getByRole("link", { name: "登入", exact: true }).click();
  await expect(page).toHaveURL(/\/login\?next=%2Fplanner$/);
  await expect(page.getByRole("heading", { name: "歡迎回來" })).toBeVisible();
  await expect(page.getByText("會員功能尚未啟用")).toBeVisible();

  await page.getByRole("banner").getByRole("link", { name: "繼續規劃" }).click();
  await expect(page.getByRole("heading", { name: "挑幾個想去的地方" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` })).toBeChecked();
  expect(api.called("/v1/trips/candidates")).toHaveLength(1);
  expect(api.unexpected).toEqual([]);
});

test("會員相關頁在未設定 Firebase 時顯示未啟用，且不呼叫 API", async ({ page }) => {
  const api = await mockApi(page);
  const id = "0190a000-0000-7000-8000-0000000000aa";
  for (const path of [
    "/register", "/forgot-password", "/verify-email", "/account", "/auth/action?mode=verifyEmail&oobCode=x",
    `/account/histories/${id}`, `/account/favorites/${id}`,
  ]) {
    await page.goto(path);
    await expect(page.getByText("會員功能尚未啟用")).toBeVisible();
  }
  expect(api.calls).toEqual([]);
});

test("刪除帳號後的結果頁不需登入：已完成與已受理兩種訊息", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/account/deleted");
  await expect(page.getByRole("heading", { name: "帳號已刪除" })).toBeVisible();
  await expect(page.getByText("您的帳號與資料已刪除")).toBeVisible();
  await page.goto("/account/deleted?status=accepted");
  await expect(page.getByRole("heading", { name: "已受理刪除帳號" })).toBeVisible();
  await expect(page.getByText("系統仍在處理中")).toBeVisible();
  await page.getByRole("link", { name: "回到首頁" }).click();
  await expect(page).toHaveURL(/\/$/);
  expect(api.calls).toEqual([]);
});

test("頁首帳號選單：圓形按鈕開合、Esc 關閉並回到按鈕、訪客顯示登入與註冊", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/");
  const banner = page.getByRole("banner");
  const trigger = banner.getByRole("button", { name: "帳號選單（未登入）", exact: true });
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(banner.getByRole("link", { name: "註冊會員" })).toBeHidden();
  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  await expect(banner.getByRole("link", { name: "登入", exact: true })).toHaveAttribute("href", "/login");
  await expect(banner.getByRole("link", { name: "註冊會員" })).toHaveAttribute("href", "/register");
  await page.keyboard.press("Escape");
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(trigger).toBeFocused();
  await trigger.click();
  await page.getByRole("main").click({ position: { x: 5, y: 5 } });
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  expect(api.unexpected).toEqual([]);
});
