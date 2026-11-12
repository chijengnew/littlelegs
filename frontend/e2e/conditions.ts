import type { Page } from "@playwright/test";
import { START } from "./mockApi";

export async function nextStep(page: Page) {
  await page.getByRole("button", { name: "下一步" }).click();
}

export async function pickStart(page: Page) {
  await page.getByRole("group", { name: "起點" }).getByRole("searchbox").fill("測試");
  await page.getByRole("button", { name: new RegExp(START.name) }).click();
}

export async function fillConditions(page: Page, age = "4") {
  await nextStep(page);
  await pickStart(page);
  await page.getByLabel("終點同起點").check();
  await nextStep(page);
  await page.getByLabel("第 1 位孩子年齡").selectOption(age);
  await nextStep(page);
}

export async function searchCandidates(page: Page, age = "4") {
  await fillConditions(page, age);
  await page.getByRole("button", { name: "搜尋候選景點" }).click();
}
