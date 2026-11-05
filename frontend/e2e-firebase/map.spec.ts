import { expect, test } from "@playwright/test";
import { login, verified } from "./accounts";

const START_QUERY = process.env.E2E_START_QUERY || "台北101";
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

test("已驗證會員：候選頁與行程頁顯示 Google 地圖，2 個景點依順序連線並註明示意；座標不寫入 sessionStorage", async ({ page }) => {
  test.skip(!verified.email || !verified.password, "未設定 E2E_VERIFIED_EMAIL／E2E_VERIFIED_PASSWORD");
  test.setTimeout(120_000);
  await login(page, verified);
  await expect(page.getByRole("banner").getByRole("link", { name: "會員" })).toBeVisible();

  await page.getByRole("group", { name: "起點" }).getByRole("searchbox").fill(START_QUERY);
  await page.getByRole("button", { name: new RegExp(escape(START_QUERY)) }).first().click();
  await page.getByLabel("第 1 位孩子年齡").selectOption("4");
  await page.getByLabel("終點同起點").check();
  await page.getByRole("button", { name: "搜尋候選景點" }).click();
  const boxes = page.getByRole("checkbox", { name: /^選擇/ });
  await expect(boxes.first()).toBeVisible({ timeout: 30_000 });
  test.skip(await page.getByText("會員地圖尚未啟用").isVisible(), "未設定 NEXT_PUBLIC_GOOGLE_MAPS_API_KEY／MAP_ID");

  const map = page.getByRole("region", { name: "地圖" });
  await expect(map).toBeVisible();
  await expect(map.getByText("候選景點")).toBeVisible();
  await expect(map.locator("gmp-advanced-marker").first()).toBeAttached({ timeout: 20_000 });
  await expect(page.getByText("地圖暫時無法載入")).toHaveCount(0);

  await boxes.nth(0).check();
  await boxes.nth(1).check();
  await page.getByRole("button", { name: "自動排出行程" }).click();
  await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible({ timeout: 30_000 });

  const planMap = page.getByRole("region", { name: "地圖" });
  await expect(planMap.getByText("順序示意，非道路導航")).toBeVisible();
  await expect(planMap.locator("gmp-advanced-marker")).toHaveCount(3, { timeout: 20_000 });
  await expect(page.getByText("地圖暫時無法載入")).toHaveCount(0);

  const stored = (await page.evaluate(() => sessionStorage.getItem("littlelegs:flow:v1"))) ?? "";
  for (const banned of ['"lat"', '"lng"', '"location"']) expect(stored).not.toContain(banned);
});
