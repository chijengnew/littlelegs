import { expect, test } from "vitest";
import { uuidv4, uuidv7 } from "./ids";

const V7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

test("UUIDv7 為小寫標準格式，前 48 位元是毫秒時間", () => {
  const ms = Date.UTC(2026, 9, 29, 2, 0, 0);
  const id = uuidv7(ms);
  expect(id).toMatch(V7);
  expect(parseInt(id.replace(/-/g, "").slice(0, 12), 16)).toBe(ms);
});

test("時間較晚的 UUIDv7 字典序較大", () => {
  expect(uuidv7(1_000) < uuidv7(2_000)).toBe(true);
});

test("session token 為 UUIDv4", () => {
  expect(uuidv4()).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});
