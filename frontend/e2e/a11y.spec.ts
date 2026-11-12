import { expect, test, type Page } from "@playwright/test";
import { MUSEUM, mockApi } from "./mockApi";
import { searchCandidates } from "./conditions";

async function audit(page: Page) {
  return page.evaluate(() => {
    const problems: string[] = [];
    const shown = (el: Element) => (el as HTMLElement).checkVisibility?.() ?? true;
    const nameOf = (el: Element) =>
      (el.getAttribute("aria-label") ||
        (el.getAttribute("aria-labelledby") ?? "")
          .split(" ")
          .map((id) => document.getElementById(id)?.textContent ?? "")
          .join("") ||
        el.textContent ||
        el.getAttribute("title") ||
        "").trim();

    if (document.documentElement.lang !== "zh-TW") problems.push(`lang=${document.documentElement.lang}`);
    for (const sel of ["main", "header", "footer"]) if (!document.querySelector(sel)) problems.push(`缺少 <${sel}>`);

    const headings = [...document.querySelectorAll("h1, h2, h3, h4")].filter(shown);
    const h1 = headings.filter((h) => h.tagName === "H1");
    if (h1.length !== 1) problems.push(`h1 數量 ${h1.length}`);
    let prev = 0;
    for (const h of headings) {
      const level = Number(h.tagName[1]);
      if (prev && level > prev + 1) problems.push(`標題跳級 h${prev}→h${level}：${h.textContent?.trim()}`);
      prev = level;
    }

    for (const el of document.querySelectorAll("a[href], button, [role='button'], [role='tab'], summary")) {
      if (shown(el) && !nameOf(el)) problems.push(`無名稱：${el.outerHTML.slice(0, 80)}`);
    }
    for (const el of document.querySelectorAll("input:not([type='hidden']), select, textarea")) {
      const field = el as HTMLInputElement;
      if (!shown(el) || field.hidden) continue;
      const labelled = (field.labels?.length ?? 0) > 0 || field.getAttribute("aria-label") || field.getAttribute("aria-labelledby");
      if (!labelled) problems.push(`欄位無標籤：${el.outerHTML.slice(0, 80)}`);
    }
    for (const svg of document.querySelectorAll("svg")) {
      if (svg.closest("[aria-hidden='true']") || svg.getAttribute("aria-hidden") === "true") continue;
      if (!svg.getAttribute("aria-label") && !svg.querySelector("title")) problems.push(`svg 未隱藏也無名稱：${svg.outerHTML.slice(0, 60)}`);
    }
    for (const img of document.querySelectorAll("img")) if (!img.hasAttribute("alt")) problems.push(`img 缺 alt：${img.src}`);
    const ids = [...document.querySelectorAll("[id]")].map((el) => el.id);
    const dup = ids.filter((id, i) => ids.indexOf(id) !== i);
    if (dup.length) problems.push(`id 重複：${[...new Set(dup)].join(", ")}`);
    return problems;
  });
}

const PAGES = [
  "/",
  "/planner",
  "/login",
  "/register",
  "/forgot-password",
  "/verify-email",
  "/auth/action?mode=verifyEmail&oobCode=x",
  "/account",
  "/account/deleted",
  `/places/${MUSEUM.place_id}`,
  "/explore/passport",
  "/explore/missions",
  "/privacy",
  "/terms",
  "/feedback",
  "/no-such-page",
];

test("各頁無障礙基本檢查：一個 h1、標題不跳級、按鈕連結與欄位都有名稱、id 不重複", async ({ page }) => {
  test.setTimeout(120_000);
  await mockApi(page);
  const report: Record<string, string[]> = {};
  for (const path of PAGES) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeAttached();
    await page.waitForLoadState("networkidle");
    const problems = await audit(page);
    if (problems.length) report[path] = problems;
  }
  expect(report).toEqual({});
});

test("規劃流程各步驟與已選抽屜的無障礙基本檢查", async ({ page }) => {
  await mockApi(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/planner");
  await searchCandidates(page);
  await page.getByRole("checkbox", { name: `選擇${MUSEUM.name}` }).check();
  expect(await audit(page), "候選頁").toEqual([]);
  await page.getByRole("button", { name: "查看" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("heading", { name: "已選景點 1／5" })).toBeFocused();
  expect(await audit(page), "已選抽屜").toEqual([]);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(page.getByRole("button", { name: "查看" })).toBeFocused();
  await page.getByRole("button", { name: "自動排出行程" }).click();
  await expect(page.getByRole("heading", { name: "時間軸" })).toBeVisible();
  expect(await audit(page), "行程頁").toEqual([]);
});

test("鍵盤：第一個 Tab 停在「跳到主要內容」，按 Enter 後焦點移到主要內容", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "跳到主要內容" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main$/);
});
