import { expect, test, type Page } from "@playwright/test";
import { MUSEUM, mockApi } from "./mockApi";

const noHorizontalScroll = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);

test("登入、註冊頁有會員說明區；忘記密碼頁是精簡置中版面，都不呼叫 API", async ({ page }) => {
  const api = await mockApi(page);
  for (const [path, heading] of [["/login", "歡迎回來"], ["/register", "註冊會員"]] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expect(page.getByRole("heading", { name: "把好行程留下來" })).toBeVisible();
    await expect(page.getByText("會員功能尚未啟用")).toBeVisible();
  }
  await page.goto("/forgot-password");
  await expect(page.getByRole("heading", { level: 1, name: "忘記密碼" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "把好行程留下來" })).toHaveCount(0);
  await expect(page.getByText("會員功能尚未啟用")).toBeVisible();
  expect(api.calls).toEqual([]);
});

test("登入、註冊頁在手機寬度只留標題，表單在說明區之前；桌機顯示插圖與好處", async ({ page }) => {
  await mockApi(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/register");
  const title = page.getByRole("heading", { name: "把好行程留下來" });
  await expect(title).toBeVisible();
  await expect(page.getByText("LittleLegs 會員")).toBeHidden();
  await expect(page.getByText("查詢會自動記在歷史紀錄")).toBeHidden();
  const titleBox = await title.boundingBox();
  const headingBox = await page.getByRole("heading", { level: 1, name: "註冊會員" }).boundingBox();
  expect(titleBox!.y).toBeLessThan(headingBox!.y);
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(page.getByText("LittleLegs 會員")).toBeVisible();
  await expect(page.getByText("查詢會自動記在歷史紀錄")).toBeVisible();
});

test("地點詳情：類型圖示與標題、地址不含郵遞區號、景點資訊四張卡片、改寫後的說明與回報連結", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto(`/places/${MUSEUM.place_id}`);
  await expect(page.getByRole("heading", { level: 1, name: MUSEUM.name })).toBeVisible();
  await expect(page.getByText("臺北市中正區測試路2號", { exact: true })).toBeVisible();
  await expect(page.getByText(/^100/)).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 2, name: "景點資訊" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 3 })).toHaveText(["適合年齡", "設施", "室內外", "類型"]);
  await expect(page.getByText("在 2F；有尿布臺", { exact: true })).toBeVisible();
  await expect(page.getByText("環境部認證場所", { exact: true })).toBeVisible();
  await expect(page.getByText(/獨立設施點位|非場勘|文化部全國博物館資料集|環署訓證字|依景點類型推定|每項資料都標示確認程度/)).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "資料來源" })).toHaveCount(0);
  const report = page.getByRole("link", { name: "發現資料有誤？告訴我們" });
  await expect(report).toBeVisible();
  await expect(report).toHaveCSS("text-decoration-line", "none");
  const facts = await page.getByRole("heading", { level: 3, name: "類型" }).boundingBox();
  expect((await report.boundingBox())!.y).toBeGreaterThan(facts!.y);
  const back = page.getByRole("link", { name: "返回", exact: true });
  await expect(back).toHaveAttribute("href", "/planner");
  await expect(back).toHaveCSS("text-decoration-line", "none");
  await expect(page.getByRole("link", { name: "回到候選景點" })).toHaveCount(0);
  expect(api.called(`/v1/places/${MUSEUM.place_id}`)).toHaveLength(1);
  expect(api.unexpected).toEqual([]);
});

for (const width of [320, 768, 1440]) {
  test(`寬度 ${width}px：會員、地點、法律與回饋頁沒有水平捲動`, async ({ page }) => {
    await mockApi(page);
    await page.setViewportSize({ width, height: 800 });
    for (const path of ["/login", "/register", "/account", `/places/${MUSEUM.place_id}`, "/privacy", "/terms", "/feedback"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      expect(await noHorizontalScroll(page), path).toBe(true);
    }
  });
}
