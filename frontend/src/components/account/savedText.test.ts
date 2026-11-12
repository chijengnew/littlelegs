import { describe, expect, test } from "vitest";
import { fullDate, isPast, statusOf, stopTypes, type SavedItem } from "./savedText";

const conditions = {
  date: "2026-11-13",
  depart_time: "09:00",
  return_time: "17:00",
  start: { type: "device_coordinate", lat: 25.03, lng: 121.56 },
  end: null,
  children_ages: [4],
} as unknown as SavedItem["conditions"];

const history = (patch: Partial<SavedItem>): SavedItem =>
  ({
    id: "h1",
    query_id: "q1",
    status: "succeeded",
    revision: 1,
    plan_ordered: false,
    conditions,
    start_label: null,
    end_label: null,
    created_at: "2026-11-12T01:00:00Z",
    updated_at: "2026-11-12T01:00:00Z",
    ...patch,
  }) as SavedItem;

describe("savedText", () => {
  test("完整日期寫成 2026/11/13（五）", () => {
    expect(fullDate("2026-11-13")).toBe("2026/11/13（五）");
    expect(fullDate("2026-11-15")).toBe("2026/11/15（日）");
    expect(fullDate("2026-11-04")).toBe("2026/11/4（三）");
  });

  test("出遊日早於今天才算過期", () => {
    expect(isPast("2026-11-04", "2026-11-12")).toBe(true);
    expect(isPast("2026-11-12", "2026-11-12")).toBe(false);
    expect(isPast("2026-11-13", "2026-11-12")).toBe(false);
  });

  test("每張卡片只留一個狀態", () => {
    expect(statusOf(history({ plan_ordered: true }))).toEqual({ key: "saved.ordered", tone: "green" });
    expect(statusOf(history({ status: "guest_imported" }))).toBeNull();
    expect(statusOf(history({ status: "succeeded" }))).toBeNull();
    expect(statusOf(history({ status: "failed" }))).toEqual({ key: "saved.status.failed", tone: "red" });
    const favorite = (saved_as: string) => ({ ...history({}), saved_as }) as unknown as SavedItem;
    expect(statusOf(favorite("plan"))).toBeNull();
    expect(statusOf(favorite("unverified"))).toEqual({ key: "saved.savedAs.unverified", tone: "amber" });
  });

  test("類型圖示依景點順序取不重複的前 3 種", () => {
    const it = history({
      stop_previews: [
        { name: "動物園", primary_type: "zoo" },
        { name: "瓶蓋工廠", primary_type: "tourism_factory" },
        { name: "另一座動物園", primary_type: "zoo" },
        { name: "博物館", primary_type: "museum" },
        { name: "公園", primary_type: "park_playground" },
      ],
    });
    expect(stopTypes(it)).toEqual(["zoo", "tourism_factory", "museum"]);
    expect(stopTypes(history({ stop_previews: [] }))).toEqual([]);
  });
});
