import { expect, test, type Page } from "@playwright/test";
import { E2E_API, mockApi } from "./mockApi";
import { fillConditions, nextStep } from "./conditions";

async function mockGooglePlace(page: Page) {
  const json = (data: unknown) => ({ status: 200, contentType: "application/json", body: JSON.stringify(data) });
  await page.route(`${E2E_API}/v1/endpoints/autocomplete`, (route) =>
    route.fulfill(json({ attribution: "Google Maps", suggestions: [{ google_place_id: "gp-101", text: "台北101" }] })),
  );
  await page.route(`${E2E_API}/v1/endpoints/resolve`, (route) =>
    route.fulfill(json({ endpoint_id: null, google_place_id: "gp-101", in_service_area: true, location: { lat: 25.0339, lng: 121.5645 } })),
  );
}

test("其他地點：選定後顯示地點名稱，有取名時改顯示名字", async ({ page }) => {
  await mockApi(page);
  await mockGooglePlace(page);
  await page.goto("/planner");
  await nextStep(page);

  const start = page.getByRole("group", { name: "起點" });
  await start.getByRole("tab", { name: "其他地點" }).click();
  await start.getByPlaceholder("輸入地址或地點名稱").fill("台北");
  await start.getByRole("button", { name: "台北101" }).click();
  await expect(page.getByText("台北101", { exact: true })).toBeVisible();
  await expect(page.getByText("自訂地點")).toHaveCount(0);

  await page.getByRole("button", { name: "重新選擇" }).click();
  await start.getByRole("tab", { name: "其他地點" }).click();
  await start.getByLabel("幫這個地點取個名字").fill("家");
  await start.getByPlaceholder("輸入地址或地點名稱").fill("台北");
  await start.getByRole("button", { name: "台北101" }).click();
  await expect(page.getByText("家", { exact: true })).toBeVisible();
});

test("時間選單以 30 分鐘為單位", async ({ page }) => {
  await mockApi(page);
  await page.goto("/planner");
  for (const label of ["出發時間", "最晚回到終點"]) {
    const select = page.getByLabel(label);
    await expect(select.locator("option")).toHaveCount(48);
    await expect(select.locator('option[value="09:30"]')).toHaveCount(1);
    await expect(select.locator('option[value="09:15"]')).toHaveCount(0);
  }

  await fillConditions(page);
  await page.getByLabel("午睡").check();
  await expect(page.locator("#f-nap-s option")).toHaveCount(48);
  await expect(page.locator("#f-nap-e option")).toHaveCount(48);
});
