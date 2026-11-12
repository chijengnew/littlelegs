import { expect, test } from "@playwright/test";
import { login, verified } from "./accounts";

const START_QUERY = process.env.E2E_START_QUERY || "台北101";
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

test("已驗證會員：在選擇景點、安排行程重新整理都會重查並停在原頁，可回到候選", async ({ page }) => {
  test.skip(!verified.email || !verified.password, "未設定 E2E_VERIFIED_EMAIL／E2E_VERIFIED_PASSWORD");
  test.setTimeout(120_000);
  await login(page, verified);
  await expect(page).toHaveURL(/\/$/);
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
  const first = page.getByRole("checkbox", { name: /^選擇/ }).first();
  await expect(first).toBeVisible({ timeout: 30_000 });
  const label = (await first.getAttribute("aria-label")) ?? "";
  await first.check();
  const picked = page.getByRole("checkbox", { name: label, exact: true });

  await page.reload();
  await expect(picked).toBeChecked({ timeout: 30_000 });

  await page.getByRole("button", { name: "自動排出行程" }).click();
  await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible({ timeout: 30_000 });
  await page.reload();
  await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("option", { hasText: "—" })).toHaveCount(0);
  await page.getByRole("button", { name: "回到候選" }).click();
  await expect(picked).toBeChecked();
});
