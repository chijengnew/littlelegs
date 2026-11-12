import { expect, test } from "@playwright/test";
import { MUSEUM, mockApi } from "./mockApi";

test("頁尾進入回饋頁：訪客可送出，只帶固定的來源類型", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/privacy");
  await expect(page.getByRole("link", { name: "chiiifortest@gmail.com" })).toHaveCount(3);
  await expect(page.getByText("待補")).toHaveCount(0);
  await page.getByRole("link", { name: "意見回饋" }).click();
  await expect(page.getByRole("heading", { name: "意見回饋" })).toBeVisible();

  await page.getByRole("button", { name: "送出回饋" }).click();
  await expect(page.getByText("請填寫內容")).toBeVisible();
  await page.getByLabel("內容").fill("  排行程很方便  ");
  await page.getByLabel("聯絡信箱").fill("not-an-email");
  await page.getByRole("button", { name: "送出回饋" }).click();
  await expect(page.getByText("聯絡信箱格式不正確")).toBeVisible();
  expect(api.called("/v1/feedback")).toHaveLength(0);

  await page.getByLabel("回饋類型").selectOption("suggestion");
  await page.getByLabel("滿意度").selectOption("5");
  await page.getByLabel("聯絡信箱").fill("a@example.com");
  await page.getByRole("button", { name: "送出回饋" }).click();
  await expect(page.getByText("已收到您的回饋，謝謝！")).toBeVisible();
  expect(api.called("/v1/feedback")[0].body).toEqual({
    type: "suggestion",
    rating: 5,
    content: "排行程很方便",
    contact_email: "a@example.com",
    source_page: "footer",
    place_id: null,
  });
  expect(api.unexpected).toEqual([]);
});

test("景點資料錯誤回報帶內部編號；不接受網址當來源", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto(`/feedback?from=place_detail&type=place_data&place=${MUSEUM.place_id}`);
  await expect(page.getByText("這則回報會附上您剛才查看的景點")).toBeVisible();
  await page.getByLabel("內容").fill("地址錯了");
  await page.getByRole("button", { name: "送出回饋" }).click();
  await expect(page.getByText("已收到您的回饋，謝謝！")).toBeVisible();
  expect(api.called("/v1/feedback")[0].body).toMatchObject({ type: "place_data", source_page: "place_detail", place_id: MUSEUM.place_id });

  await page.goto(`/feedback?from=${encodeURIComponent("/account/favorites/abc")}`);
  await page.getByLabel("內容").fill("其他");
  await page.getByRole("button", { name: "送出回饋" }).click();
  await expect(page.getByText("已收到您的回饋，謝謝！")).toBeVisible();
  const last = api.called("/v1/feedback").at(-1)?.body;
  expect(last).toMatchObject({ source_page: "other", place_id: null });
  expect(JSON.stringify(last)).not.toContain("account");
});

test("送出太頻繁時顯示易懂的提示，已填內容還在", async ({ page }) => {
  await mockApi(page, { feedbackLimit: 0 });
  await page.goto("/feedback?from=footer");
  await page.getByLabel("內容").fill("想要更多景點");
  await page.getByRole("button", { name: "送出回饋" }).click();
  await expect(page.getByText("送出太頻繁，請稍等一分鐘再試")).toBeVisible();
  await expect(page.getByLabel("內容")).toHaveValue("想要更多景點");
});

test("從地點頁進入：預選景點資料錯誤並附上景點", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto(`/places/${MUSEUM.place_id}`);
  await page.getByRole("link", { name: "發現資料有誤？告訴我們" }).click();
  await expect(page.getByLabel("回饋類型")).toHaveValue("place_data");
  await expect(page.getByText("這則回報會附上您剛才查看的景點")).toBeVisible();
  await page.getByLabel("內容").fill("地址錯了");
  await page.getByRole("button", { name: "送出回饋" }).click();
  await expect(page.getByText("已收到您的回饋，謝謝！")).toBeVisible();
  expect(api.called("/v1/feedback")[0].body).toMatchObject({ type: "place_data", source_page: "place_detail", place_id: MUSEUM.place_id });
});

test("先從頁尾進過回饋頁，再從地點頁進入：仍預選景點資料錯誤", async ({ page }) => {
  await mockApi(page);
  await page.goto(`/places/${MUSEUM.place_id}`);
  await page.getByRole("link", { name: "意見回饋" }).click();
  await expect(page.getByLabel("回饋類型")).toHaveValue("bug");
  await page.goBack();
  await page.getByRole("link", { name: "發現資料有誤？告訴我們" }).click();
  await expect(page.getByLabel("回饋類型")).toHaveValue("place_data");
  await expect(page.getByText("這則回報會附上您剛才查看的景點")).toBeVisible();
});

test("送出後離開再回來：看到新的表單，不是上一次的完成畫面", async ({ page }) => {
  await mockApi(page);
  await page.goto("/privacy");
  await page.getByRole("link", { name: "意見回饋" }).click();
  await page.getByLabel("內容").fill("第一則");
  await page.getByRole("button", { name: "送出回饋" }).click();
  await expect(page.getByText("已收到您的回饋，謝謝！")).toBeVisible();
  await page.getByRole("link", { name: "隱私權與個資告知" }).click();
  await page.getByRole("link", { name: "意見回饋" }).click();
  await expect(page.getByLabel("內容")).toHaveValue("");
  await expect(page.getByText("已收到您的回饋，謝謝！")).toHaveCount(0);
});
