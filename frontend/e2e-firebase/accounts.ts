import { expect, type Page } from "@playwright/test";

const env = process.env;
export const verified = { email: env.E2E_VERIFIED_EMAIL ?? "", password: env.E2E_VERIFIED_PASSWORD ?? "" };
export const unverified = { email: env.E2E_UNVERIFIED_EMAIL ?? "", password: env.E2E_UNVERIFIED_PASSWORD ?? "" };

export async function login(page: Page, who: { email: string; password: string }) {
  await page.goto("/login");
  await page.getByLabel("電子郵件").fill(who.email);
  await page.getByLabel("密碼", { exact: true }).fill(who.password);
  await page.getByRole("button", { name: "登入", exact: true }).click();
}

export async function logout(page: Page) {
  await page.getByRole("button", { name: "登出" }).click();
  await expect(page.getByRole("banner").getByRole("button", { name: "帳號選單（未登入）", exact: true })).toBeVisible();
}
