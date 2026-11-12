import { expect, test } from "@playwright/test";
import { CENTER, MUSEUM, START, mockApi } from "./mockApi";
import { nextStep, pickStart, searchCandidates } from "./conditions";

test("訪客：條件 → 候選 → 自動排序 → 調整後按檢查才重算", async ({ page }) => {
  const api = await mockApi(page);
  const mapRequests: string[] = [];
  await page.route("https://maps.googleapis.com/**", (route) => {
    mapRequests.push(route.request().url());
    return route.abort();
  });
  await page.goto("/planner");

  await searchCandidates(page);

  await expect(page.getByRole("heading", { name: "挑幾個想去的地方" })).toBeVisible();
  const [search] = api.called("/v1/trips/candidates");
  const queryId = search.body?.query_id;
  expect(queryId).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  expect(search.body?.conditions).toMatchObject({ children_ages: [4], start: { type: "place_ref", place_id: START.place_id } });

  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();
  await page.getByRole("checkbox", { name: `選擇${CENTER.name}` }).check();
  await page.getByRole("button", { name: "自動排出行程" }).click();

  await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "您的一天" })).toBeVisible();
  expect(api.called("/v1/trips/sort")).toHaveLength(1);
  await expect(page.getByRole("button", { name: /收藏行程/ })).toBeDisabled();

  const apiCalls = api.called("/v1/trips/sort").length + api.called("/v1/trips/check").length;
  const nav = page.getByRole("link", { name: "使用 Google 地圖導航", exact: true });
  await expect(nav).toHaveAttribute("target", "_blank");
  const url = new URL((await nav.getAttribute("href")) ?? "");
  expect(url.origin + url.pathname).toBe("https://www.google.com/maps/dir/");
  expect(url.searchParams.get("destination")).toBe(CENTER.name);
  expect(url.searchParams.get("destination_place_id")).toBe(`ChIJ${CENTER.place_id.slice(-4)}`);
  expect(url.searchParams.get("origin")).toBeNull();
  await expect(page.getByRole("link", { name: `使用 Google 地圖導航到${CENTER.name}` })).toBeVisible();
  await expect(page.getByText("實際路線和時間以 Google 地圖為準。")).toBeVisible();
  expect(api.called("/v1/trips/sort").length + api.called("/v1/trips/check").length).toBe(apiCalls);

  await page.getByRole("button", { name: "調整順序與時間" }).click();
  await expect(page.getByRole("button", { name: `將${CENTER.name}往前移` })).toBeDisabled();
  await page.getByLabel(`${MUSEUM.name}停留時間（分鐘）`).selectOption("120");
  await expect(page.getByText("有調整，尚未檢查")).toBeVisible();
  expect(api.called("/v1/trips/check")).toHaveLength(0);
  await expect(nav).toHaveCount(0);

  await page.getByRole("button", { name: "檢查這個行程" }).click();
  await expect(page.getByText("已手動調整")).toBeVisible();
  const checks = api.called("/v1/trips/check");
  expect(checks).toHaveLength(1);
  expect(checks[0].body).toMatchObject({
    query_id: queryId,
    stops: [
      { place_id: CENTER.place_id, stay_minutes: null },
      { place_id: MUSEUM.place_id, stay_minutes: 120 },
    ],
  });

  const stored = await page.evaluate(() => sessionStorage.getItem("littlelegs:flow:v1"));
  expect(stored).toContain(String(queryId));
  for (const banned of ["timeline", "feasibility", "duration_s", "distance_m"]) expect(stored).not.toContain(banned);
  expect(api.unexpected).toEqual([]);

  await expect(page.getByText("登入後可以在地圖上看路線")).toBeVisible();
  expect(mapRequests).toEqual([]);
});

test("訪客：必填欄位未填時不能進下一步，也不送出任何查詢；上一步保留已選內容", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/planner");
  await expect(page.getByRole("heading", { name: "什麼時候出發？" })).toBeVisible();
  await nextStep(page);
  await expect(page.getByRole("heading", { name: "從哪裡出發？" })).toBeVisible();
  await nextStep(page);
  await expect(page.getByText("請選擇起點")).toBeVisible();
  await expect(page.getByText("請選擇終點")).toBeVisible();
  await expect(page.getByRole("heading", { name: "從哪裡出發？" })).toBeVisible();
  await pickStart(page);
  await page.getByLabel("終點同起點").check();
  await nextStep(page);
  await expect(page.getByRole("heading", { name: "誰一起出門？" })).toBeVisible();
  await expect(page.getByText("請選擇起點")).toHaveCount(0);
  await nextStep(page);
  await expect(page.locator("#err-children")).toBeVisible();
  await expect(page.getByLabel("第 1 位孩子年齡")).toBeFocused();
  await page.getByLabel("第 1 位孩子年齡").selectOption("4");
  await nextStep(page);
  await expect(page.getByRole("heading", { name: "還有什麼要考慮？" })).toBeVisible();
  await expect(page.getByRole("button", { name: "搜尋候選景點" })).toBeVisible();
  await page.getByRole("button", { name: "上一步" }).click();
  await expect(page.getByLabel("第 1 位孩子年齡")).toHaveValue("4");
  await page.getByRole("button", { name: "上一步" }).click();
  await expect(page.getByLabel("終點同起點")).toBeChecked();
  await expect(page.getByRole("button", { name: "重新選擇" })).toBeVisible();
  expect(api.called("/v1/trips/candidates")).toEqual([]);
  expect(api.unexpected).toEqual([]);
});

test("訪客：步驟列不可點選；修改條件讓所有條件回到預設值，重新填同樣條件後搜尋會清空勾選、query_id 不變", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/planner");
  const date = page.getByLabel("出遊日期");
  const defaultDate = await date.inputValue();
  const lastDate = (await date.getAttribute("max")) ?? "";
  await date.fill(lastDate);
  await page.getByLabel("出發時間").selectOption("10:00");
  await nextStep(page);
  await pickStart(page);
  await page.getByLabel("終點同起點").check();
  await nextStep(page);
  await page.getByLabel("第 1 位孩子年齡").selectOption("4");
  await nextStep(page);
  await page.getByLabel("下雨只排室內").check();
  await page.getByRole("button", { name: "搜尋候選景點" }).click();
  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();

  const stepper = page.getByRole("list", { name: "查詢步驟" });
  await expect(stepper.getByRole("button")).toHaveCount(0);
  await expect(stepper.locator("[aria-current='step']")).toHaveText(/選擇景點/);

  await page.getByRole("button", { name: "修改條件" }).click();
  await expect(stepper.locator("[aria-current='step']")).toHaveText(/設定條件/);
  await expect(page.getByRole("heading", { name: "什麼時候出發？" })).toBeVisible();
  await expect(date).toHaveValue(defaultDate);
  await expect(page.getByLabel("出發時間")).toHaveValue("09:00");
  await nextStep(page);
  await expect(page.getByRole("group", { name: "起點" }).getByRole("tab", { name: "景點／飯店" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("group", { name: "起點" }).getByRole("searchbox")).toHaveValue("");
  await expect(page.getByRole("button", { name: "重新選擇" })).toHaveCount(0);
  await expect(page.getByLabel("終點同起點")).not.toBeChecked();
  await pickStart(page);
  await page.getByLabel("終點同起點").check();
  await nextStep(page);
  await expect(page.getByLabel("第 1 位孩子年齡")).toHaveValue("");
  await page.getByLabel("第 1 位孩子年齡").selectOption("4");
  await nextStep(page);
  await expect(page.getByLabel("下雨只排室內")).not.toBeChecked();
  expect(api.called("/v1/trips/candidates")).toHaveLength(1);

  await page.getByLabel("下雨只排室內").check();
  await page.getByRole("button", { name: "修改日期與時間" }).click();
  await expect(page.getByRole("heading", { name: "什麼時候出發？" })).toBeVisible();
  await date.fill(lastDate);
  await page.getByLabel("出發時間").selectOption("10:00");
  await page.getByRole("button", { name: "完成" }).click();
  await expect(page.getByLabel("下雨只排室內")).toBeChecked();
  await page.getByRole("button", { name: "搜尋候選景點" }).click();
  await expect(page.getByText("已選 0／5")).toBeVisible();
  await expect(page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` })).not.toBeChecked();
  const searches = api.called("/v1/trips/candidates");
  expect(searches).toHaveLength(2);
  expect(searches[1].body?.query_id).toBe(searches[0].body?.query_id);
  expect(api.unexpected).toEqual([]);
});

test("訪客：準備清單依條件產生，勾選留在這次流程、不寫入 localStorage", async ({ page }) => {
  await mockApi(page);
  await page.goto("/planner");
  await searchCandidates(page);
  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();
  await page.getByRole("button", { name: "自動排出行程" }).click();
  const packing = page.getByRole("button", { name: /出遊準備清單/ });
  await expect(packing).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByRole("checkbox", { name: "點心" })).toBeHidden();
  await packing.click();

  await expect(page.getByRole("checkbox", { name: "點心" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "尿布（依需要）" })).toHaveCount(0);
  await expect(page.getByRole("checkbox", { name: "雨衣或雨傘（選用）" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "備用鞋襪" })).toHaveCount(0);
  await page.getByRole("checkbox", { name: "預計會下雨，顯示雨天用品" }).check();
  await expect(page.getByRole("checkbox", { name: "備用鞋襪" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "雨衣或雨傘（選用）" })).toHaveCount(0);

  await page.getByRole("checkbox", { name: "點心" }).check();
  await page.getByRole("button", { name: "移除小玩具" }).click();
  await expect(page.getByRole("checkbox", { name: "小玩具" })).toHaveCount(0);

  await page.reload();
  await page.getByRole("button", { name: /出遊準備清單/ }).click();
  await expect(page.getByRole("checkbox", { name: "點心" })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: "小玩具" })).toHaveCount(0);
  const keys = await page.evaluate(() => ({
    session: Object.keys(sessionStorage).filter((k) => k.includes("packing")),
    local: Object.keys(localStorage).filter((k) => k.includes("packing")),
  }));
  expect(keys.session).toHaveLength(1);
  expect(keys.local).toHaveLength(0);

  await page.getByRole("button", { name: "還原已移除的 1 項" }).click();
  await expect(page.getByRole("checkbox", { name: "小玩具" })).toBeVisible();
});

test("從已選條件修改：按鈕改為完成，重新整理後仍是完成，按完成直接回到時段與偏好", async ({ page }) => {
  await mockApi(page);
  await page.goto("/planner");
  await nextStep(page);
  await pickStart(page);
  await page.getByLabel("終點同起點").check();
  await nextStep(page);
  await page.getByLabel("第 1 位孩子年齡").selectOption("4");
  await nextStep(page);

  await page.getByRole("button", { name: "修改日期與時間" }).click();
  await expect(page.getByRole("heading", { name: "什麼時候出發？" })).toBeVisible();
  await expect(page.getByRole("button", { name: "完成" })).toBeVisible();
  await expect(page.getByRole("button", { name: "上一步" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "下一步" })).toHaveCount(0);
  const progress = page.getByRole("list", { name: "條件設定進度" });
  await expect(progress.getByRole("listitem").nth(1)).toContainText("已完成");
  await expect(progress.getByRole("listitem").nth(2)).toContainText("已完成");
  await expect(progress.getByRole("listitem").nth(3)).not.toContainText("已完成");
  await page.locator("#f-depart").selectOption("10:00");

  await page.reload();
  await expect(page.getByRole("heading", { name: "什麼時候出發？" })).toBeVisible();
  await expect(page.getByRole("button", { name: "完成" })).toBeVisible();
  await expect(page.locator("#f-depart")).toHaveValue("10:00");

  await page.getByRole("button", { name: "完成" }).click();
  await expect(page.getByRole("heading", { name: "還有什麼要考慮？" })).toBeVisible();
  await expect(page.getByText(/10:00–17:00/)).toBeVisible();
  await expect(page.getByRole("button", { name: "上一步" })).toBeVisible();

  await page.getByRole("button", { name: "上一步" }).click();
  await expect(page.getByRole("heading", { name: "誰一起出門？" })).toBeVisible();
  await expect(page.getByRole("button", { name: "下一步" })).toBeVisible();
});

test("搜尋候選後回首頁：頁首與首頁按鈕改為繼續規劃，回到原畫面且不重新查詢；修改條件後恢復開始規劃", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/planner");
  await searchCandidates(page);
  await expect(page.getByRole("heading", { name: "挑幾個想去的地方" })).toBeVisible();
  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();

  await page.getByRole("link", { name: "LittleLegs" }).click();
  await expect(page.getByRole("link", { name: "繼續規劃" })).toHaveCount(3);
  await expect(page.getByRole("link", { name: "開始規劃" })).toHaveCount(0);
  await page.getByRole("main").getByRole("link", { name: "繼續規劃" }).first().click();
  await expect(page.getByRole("heading", { name: "挑幾個想去的地方" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` })).toBeChecked();
  expect(api.called("/v1/trips/candidates")).toHaveLength(1);

  await page.getByRole("button", { name: "修改條件" }).click();
  await page.getByRole("link", { name: "LittleLegs" }).click();
  await expect(page.getByRole("link", { name: "開始規劃" })).toHaveCount(3);
  expect(api.unexpected).toEqual([]);
});

test("規劃入口：沒動過顯示開始規劃；改過欄位或走到第 2 步就顯示繼續規劃並回到原位；清除條件重新開始只在有內容時出現", async ({ page }) => {
  await mockApi(page);
  await page.goto("/planner");
  await expect(page.getByRole("button", { name: "清除條件重新開始" })).toHaveCount(0);
  await page.getByRole("link", { name: "LittleLegs" }).click();
  await expect(page.getByRole("link", { name: "開始規劃" })).toHaveCount(3);

  await page.getByRole("banner").getByRole("link", { name: "開始規劃" }).click();
  await page.getByLabel("出發時間").selectOption("10:00");
  await expect(page.getByRole("button", { name: "清除條件重新開始" })).toBeVisible();
  await page.getByRole("link", { name: "LittleLegs" }).click();
  await expect(page.getByRole("link", { name: "繼續規劃" })).toHaveCount(3);

  await page.getByRole("banner").getByRole("link", { name: "繼續規劃" }).click();
  await expect(page.getByLabel("出發時間")).toHaveValue("10:00");
  await page.getByRole("button", { name: "清除條件重新開始" }).click();
  await expect(page.getByLabel("出發時間")).toHaveValue("09:00");
  await expect(page.getByRole("button", { name: "清除條件重新開始" })).toHaveCount(0);

  await nextStep(page);
  await expect(page.getByRole("heading", { name: "從哪裡出發？" })).toBeVisible();
  await page.getByRole("link", { name: "LittleLegs" }).click();
  await expect(page.getByRole("link", { name: "繼續規劃" })).toHaveCount(3);
  await page.reload();
  await expect(page.getByRole("link", { name: "繼續規劃" })).toHaveCount(3);
  await page.getByRole("main").getByRole("link", { name: "繼續規劃" }).first().click();
  await expect(page.getByRole("heading", { name: "從哪裡出發？" })).toBeVisible();
});

test("修改條件後回到全新的第 1 步，不顯示清除條件重新開始", async ({ page }) => {
  await mockApi(page);
  await page.goto("/planner");
  await searchCandidates(page);
  await page.getByRole("button", { name: "修改條件" }).click();
  await expect(page.getByRole("heading", { name: "什麼時候出發？" })).toBeVisible();
  await expect(page.getByRole("button", { name: "清除條件重新開始" })).toHaveCount(0);
});
