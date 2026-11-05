import { expect, test } from "@playwright/test";
import { MUSEUM, START, mockApi } from "./mockApi";

test("中途去登入頁再回來：候選與已選景點仍在，不重新查詢", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/");
  await page.getByRole("group", { name: "起點" }).getByRole("searchbox").fill("測試");
  await page.getByRole("button", { name: new RegExp(START.name) }).click();
  await page.getByLabel("第 1 位孩子年齡").selectOption("4");
  await page.getByLabel("終點同起點").check();
  await page.getByRole("button", { name: "搜尋候選景點" }).click();
  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();

  await page.getByRole("banner").getByRole("link", { name: "登入" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "登入" })).toBeVisible();
  await expect(page.getByText("會員功能尚未啟用")).toBeVisible();

  await page.getByRole("link", { name: "littlelegs" }).click();
  await expect(page.getByRole("heading", { name: "候選景點" })).toBeVisible();
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
  await expect(page.getByText("你的帳號與資料已刪除")).toBeVisible();
  await page.goto("/account/deleted?status=accepted");
  await expect(page.getByText("已受理刪除帳號")).toBeVisible();
  await page.getByRole("link", { name: "回到首頁" }).click();
  await expect(page).toHaveURL(/\/$/);
  expect(api.calls).toEqual([]);
});
