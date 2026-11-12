import { expect, test } from "@playwright/test";
import { login, verified } from "./accounts";

test("註冊後不驗證：取消註冊會刪除帳號，回到原頁面且查詢條件不保留", async ({ page }) => {
  test.skip(!verified.email.includes("@"), "未設定 E2E_VERIFIED_EMAIL");
  const [user, domain] = verified.email.split("@");
  const stamp = Date.now();
  const who = { email: `${user.split("+")[0]}+e2e-reg-${stamp}@${domain}`, password: `e2e-reg-${stamp}` };

  await page.goto("/planner");
  await page.getByLabel("出發時間").selectOption("10:00");
  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByLabel("終點同起點").check();
  await page.getByRole("banner").getByRole("button", { name: "帳號選單（未登入）", exact: true }).click();
  await page.getByRole("banner").getByRole("link", { name: "登入", exact: true }).click();
  await page.getByRole("link", { name: "註冊會員" }).click();
  await page.getByLabel("電子郵件").fill(who.email);
  await page.getByLabel("密碼", { exact: true }).fill(who.password);
  await page.getByRole("button", { name: "註冊並寄出驗證信" }).click();
  await expect(page).toHaveURL(/\/verify-email/);
  await expect(page.getByText(`驗證信已寄到 ${who.email}`)).toBeVisible();

  await page.getByRole("banner").getByRole("link", { name: "LittleLegs" }).click();
  await expect(page).toHaveURL(/\/verify-email$/);

  await page.getByRole("button", { name: "取消註冊" }).click();
  await page.getByRole("button", { name: "確定取消註冊" }).click();
  await expect(page).toHaveURL(/\/planner$/);
  await expect(page.getByRole("banner").getByRole("button", { name: "帳號選單（未登入）", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "什麼時候出發？" })).toBeVisible();
  await expect(page.getByLabel("出發時間")).toHaveValue("09:00");
  await page.getByRole("button", { name: "下一步" }).click();
  await expect(page.getByLabel("終點同起點")).not.toBeChecked();

  await login(page, who);
  await expect(page.getByText("電子郵件或密碼不正確。")).toBeVisible();
});
