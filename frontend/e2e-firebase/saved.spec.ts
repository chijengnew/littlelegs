import { expect, test } from "@playwright/test";
import { login, verified } from "./accounts";

const START_QUERY = process.env.E2E_START_QUERY || "台北101";
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

test("已驗證會員：收藏行程 → 會員頁收藏列表 → 詳細頁 → 刪除；歷史分頁有這次查詢", async ({ page }) => {
  test.skip(!verified.email || !verified.password, "未設定 E2E_VERIFIED_EMAIL／E2E_VERIFIED_PASSWORD");
  test.setTimeout(120_000);
  await login(page, verified);
  await expect(page.getByRole("banner").getByRole("button", { name: "帳號選單（會員）", exact: true })).toBeVisible();
  await page.goto("/planner");

  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("group", { name: "起點" }).getByRole("searchbox").fill(START_QUERY);
  await page.getByRole("button", { name: new RegExp(escape(START_QUERY)) }).first().click();
  await page.getByLabel("終點同起點").check();
  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByLabel("第 1 位孩子年齡").selectOption("4");
  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "搜尋候選景點" }).click();
  await page.getByRole("checkbox", { name: /^選擇/ }).first().check({ timeout: 30_000 });
  await page.getByRole("button", { name: "自動排出行程" }).click();
  await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: /收藏行程/ }).click();
  const confirm = page.getByRole("button", { name: "仍要保存" });
  if (await confirm.isVisible().catch(() => false)) await confirm.click();
  await expect(page.getByText(/已收藏/)).toBeVisible({ timeout: 15_000 });

  await page.getByRole("link", { name: "到我的行程查看" }).click();
  await expect(page).toHaveURL(/tab=favorites/);
  await page.locator("#account-panel").getByRole("link").first().click();
  await expect(page.getByRole("heading", { name: "收藏的行程" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "景點順序與停留時間" })).toBeVisible();
  await page.getByRole("button", { name: "刪除", exact: true }).click();
  await page.getByRole("button", { name: "確定刪除" }).click();
  await expect(page.getByText(/已刪除|已受理刪除/)).toBeVisible({ timeout: 15_000 });

  await page.getByRole("navigation", { name: "會員中心導覽" }).getByRole("link", { name: "歷史" }).click();
  await expect(page.locator("#account-panel").getByRole("link").first()).toBeVisible();
});
