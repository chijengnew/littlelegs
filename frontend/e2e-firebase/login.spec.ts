import { expect, test } from "@playwright/test";
import { login, logout, unverified, verified } from "./accounts";

test("已驗證帳號：登入、會員頁顯示已驗證、登出", async ({ page }) => {
  test.skip(!verified.email || !verified.password, "未設定 E2E_VERIFIED_EMAIL／E2E_VERIFIED_PASSWORD");
  await login(page, verified);
  await expect(page).toHaveURL(/\/$/);
  await page.getByRole("banner").getByRole("button", { name: "帳號選單（會員）", exact: true }).click();
  await page.getByRole("banner").getByRole("link", { name: "帳號", exact: true }).click();
  await expect(page.getByText(verified.email)).toBeVisible();
  await expect(page.getByText("已驗證", { exact: true })).toBeVisible();
  await logout(page);
});

test("未驗證帳號（註冊未完成）：只能停在驗證頁；登出後再登入仍回到驗證頁", async ({ page }) => {
  test.skip(!unverified.email || !unverified.password, "未設定 E2E_UNVERIFIED_EMAIL／E2E_UNVERIFIED_PASSWORD");
  await login(page, unverified);
  await expect(page).toHaveURL(/\/verify-email/);
  await expect(page.getByRole("heading", { name: "驗證您的 Email" })).toBeVisible();
  await expect(page.getByRole("button", { name: "我已完成驗證" })).toBeVisible();
  await expect(page.getByRole("button", { name: "取消註冊" })).toBeVisible();
  await page.goto("/account");
  await expect(page).toHaveURL(/\/verify-email\?next=%2Faccount$/);
  await page.goto("/");
  await expect(page).toHaveURL(/\/verify-email$/);
  await logout(page);
  await expect(page).toHaveURL(/\/$/);
  await login(page, unverified);
  await expect(page).toHaveURL(/\/verify-email/);
  await page.goto("/account");
  await expect(page).toHaveURL(/\/verify-email\?next=%2Faccount$/);
});

test("密碼錯誤顯示一般訊息", async ({ page }) => {
  test.skip(!verified.email, "未設定 E2E_VERIFIED_EMAIL");
  await login(page, { email: verified.email, password: "wrong-password-e2e" });
  await expect(page.getByText("電子郵件或密碼不正確。")).toBeVisible();
});

test("忘記密碼：不論帳號是否存在都顯示相同訊息", async ({ page }) => {
  test.skip(!verified.email.includes("@"), "未設定 E2E_VERIFIED_EMAIL");
  const [user, domain] = verified.email.split("@");
  await page.goto("/forgot-password");
  await page.getByLabel("電子郵件").fill(`${user.split("+")[0]}+e2e-nobody@${domain}`);
  await page.getByRole("button", { name: "寄出重設信" }).click();
  await expect(page.getByText("如果這個信箱有註冊，幾分鐘內會收到重設密碼的信")).toBeVisible();
});
