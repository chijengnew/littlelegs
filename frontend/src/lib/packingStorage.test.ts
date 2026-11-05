import { afterEach, beforeEach, expect, test, vi } from "vitest";
import {
  MAX_CUSTOM_ITEMS,
  adoptGuestPacking,
  clearGuestPacking,
  emptyPacking,
  favoriteListId,
  linkFavoritePacking,
  loadPacking,
  purgeOtherMembers,
  queryListId,
  removeFavoritePacking,
  removeHistoryPacking,
  savePacking,
} from "./packingStorage";

function storage() {
  const m = new Map<string, string>();
  return {
    get length() {
      return m.size;
    },
    key: (i: number) => [...m.keys()][i] ?? null,
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
    removeItem: (k: string) => void m.delete(k),
  };
}

let local: ReturnType<typeof storage>;
let session: ReturnType<typeof storage>;
const Q = queryListId("q1");
const F = favoriteListId("f1");
const checked = (...ids: string[]) => ({ ...emptyPacking(), checked: ids });

beforeEach(() => {
  local = storage();
  session = storage();
  vi.stubGlobal("localStorage", local);
  vi.stubGlobal("sessionStorage", session);
});
afterEach(() => vi.unstubAllGlobals());

test("訪客只寫 sessionStorage，會員只寫 localStorage", () => {
  savePacking(null, Q, checked("a"));
  expect([session.length, local.length]).toEqual([1, 0]);
  savePacking("u1", Q, checked("b"));
  expect([session.length, local.length]).toEqual([1, 1]);
  expect(loadPacking(null, Q).checked).toEqual(["a"]);
  expect(loadPacking("u1", Q).checked).toEqual(["b"]);
});

test("依會員與行程隔離", () => {
  savePacking("u1", Q, checked("a"));
  expect(loadPacking("u2", Q).checked).toEqual([]);
  expect(loadPacking("u1", queryListId("q2")).checked).toEqual([]);
});

test("登出清除所有會員清單；切換帳號只留目前會員", () => {
  savePacking("u1", Q, checked("a"));
  savePacking("u2", Q, checked("b"));
  linkFavoritePacking("u1", "f1", "q1");
  purgeOtherMembers("u2");
  expect(loadPacking("u1", Q).checked).toEqual([]);
  expect(loadPacking("u2", Q).checked).toEqual(["b"]);
  expect(local.length).toBe(1);
  purgeOtherMembers(null);
  expect(local.length).toBe(0);
});

test("會員 UID 開頭相同時不互相誤判", () => {
  savePacking("u1", Q, checked("a"));
  savePacking("u10", Q, checked("b"));
  purgeOtherMembers("u1");
  expect(loadPacking("u1", Q).checked).toEqual(["a"]);
  expect(loadPacking("u10", Q).checked).toEqual([]);
});

test("清除只影響準備清單，不動其他資料", () => {
  local.setItem("other", "1");
  session.setItem("littlelegs:flow:v1", "{}");
  savePacking(null, Q, checked("a"));
  purgeOtherMembers(null);
  clearGuestPacking();
  expect(local.getItem("other")).toBe("1");
  expect(session.getItem("littlelegs:flow:v1")).toBe("{}");
  expect(loadPacking(null, Q).checked).toEqual([]);
});

test("訪客中途登入：同一 query_id 的勾選帶到會員，訪客暫存清除", () => {
  savePacking(null, Q, checked("a"));
  adoptGuestPacking("u1", Q);
  expect(loadPacking("u1", Q).checked).toEqual(["a"]);
  expect(session.length).toBe(0);
});

test("中途登入時會員已有清單就保留會員的", () => {
  savePacking("u1", Q, checked("member"));
  savePacking(null, Q, checked("guest"));
  adoptGuestPacking("u1", Q);
  expect(loadPacking("u1", Q).checked).toEqual(["member"]);
  expect(session.length).toBe(0);
});

test("收藏後與規劃中的行程共用同一份清單，雙向一致", () => {
  savePacking("u1", Q, checked("a"));
  linkFavoritePacking("u1", "f1", "q1");
  expect(loadPacking("u1", F).checked).toEqual(["a"]);
  savePacking("u1", F, checked("a", "b"));
  expect(loadPacking("u1", Q).checked).toEqual(["a", "b"]);
});

test("重複收藏不覆蓋收藏原本的清單", () => {
  savePacking("u1", F, checked("old"));
  savePacking("u1", Q, checked("new"));
  linkFavoritePacking("u1", "f1", "q1");
  expect(loadPacking("u1", F).checked).toEqual(["old"]);
});

test("刪除歷史：連結的收藏保留自己的一份，歷史那份清除", () => {
  savePacking("u1", Q, checked("a"));
  linkFavoritePacking("u1", "f1", "q1");
  removeHistoryPacking("u1", "q1");
  expect(loadPacking("u1", F).checked).toEqual(["a"]);
  expect(loadPacking("u1", Q).checked).toEqual([]);
  expect(local.length).toBe(1);
});

test("刪除收藏：只移除收藏的連結，歷史的清單保留", () => {
  savePacking("u1", Q, checked("a"));
  linkFavoritePacking("u1", "f1", "q1");
  removeFavoritePacking("u1", "f1");
  expect(loadPacking("u1", F).checked).toEqual([]);
  expect(loadPacking("u1", Q).checked).toEqual(["a"]);
});

test("還原內容視為不可信：格式錯誤回空清單、過濾非法欄位、限制自訂項目", () => {
  session.setItem("littlelegs:packing:v1:guest:q:bad", "{not json");
  expect(loadPacking(null, "q:bad")).toEqual(emptyPacking());
  const custom = Array.from({ length: MAX_CUSTOM_ITEMS + 5 }, (_, i) => ({ id: `c${i}`, label: "x".repeat(99) }));
  session.setItem(
    "littlelegs:packing:v1:guest:q:odd",
    JSON.stringify({ checked: ["a", 1], removed: "no", custom: [...custom, { id: 1 }], expectRain: "yes" }),
  );
  const v = loadPacking(null, "q:odd");
  expect(v.checked).toEqual(["a"]);
  expect(v.removed).toEqual([]);
  expect(v.expectRain).toBe(false);
  expect(v.custom).toHaveLength(MAX_CUSTOM_ITEMS);
  expect(v.custom[0].label).toHaveLength(40);
});

test("儲存空間無法使用時不丟出例外", () => {
  vi.stubGlobal("localStorage", undefined);
  vi.stubGlobal("sessionStorage", undefined);
  expect(loadPacking("u1", Q)).toEqual(emptyPacking());
  expect(() => savePacking("u1", Q, checked("a"))).not.toThrow();
  expect(() => purgeOtherMembers(null)).not.toThrow();
  expect(() => clearGuestPacking()).not.toThrow();
  expect(() => adoptGuestPacking("u1", Q)).not.toThrow();
  expect(() => linkFavoritePacking("u1", "f", "q")).not.toThrow();
  expect(() => removeHistoryPacking("u1", "q")).not.toThrow();
  expect(() => removeFavoritePacking("u1", "f")).not.toThrow();
});
