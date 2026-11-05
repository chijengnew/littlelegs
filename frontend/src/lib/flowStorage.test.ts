import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { clearFlow, loadFlow, saveFlow, type StoredFlow } from "./flowStorage";
import { initialForm } from "./form";

const KEY = "littlelegs:flow:v1";
let store: Map<string, string>;

beforeEach(() => {
  store = new Map();
  vi.stubGlobal("sessionStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  });
});
afterEach(() => vi.unstubAllGlobals());

const flow: StoredFlow = {
  form: initialForm(new Date("2026-10-29T02:00:00Z")),
  queryId: "0190a000-0000-7000-8000-0000000000aa",
  submittedKey: "{}",
  selection: [{ place_id: "0190a000-0000-7000-8000-000000000002", name: "測試博物館", stay_minutes: null, default_stay_minutes: 90 }],
  ownerUid: null,
  searched: true,
  ordered: true,
  step: "plan",
  planMode: "sort",
  dirty: true,
};

test("保存後可還原，清除後為 null", () => {
  saveFlow(flow);
  expect(loadFlow()).toEqual(flow);
  clearFlow();
  expect(loadFlow()).toBeNull();
});

test("還原內容視為不可信：格式錯誤時回 null", () => {
  store.set(KEY, "{not json");
  expect(loadFlow()).toBeNull();
  store.set(KEY, JSON.stringify({ form: null, selection: [] }));
  expect(loadFlow()).toBeNull();
  store.set(KEY, JSON.stringify({ form: {}, selection: "x" }));
  expect(loadFlow()).toBeNull();
});

test("無法使用 sessionStorage 時不拋錯", () => {
  vi.stubGlobal("sessionStorage", {
    getItem: () => { throw new Error("blocked"); },
    setItem: () => { throw new Error("blocked"); },
    removeItem: () => { throw new Error("blocked"); },
  });
  expect(() => saveFlow(flow)).not.toThrow();
  expect(loadFlow()).toBeNull();
  expect(() => clearFlow()).not.toThrow();
});
