import { describe, expect, test } from "vitest";
import type { Conditions } from "./api/client";
import { toConditions } from "./form";
import { conditionsToForm, endpointName, recheckBlock } from "./saved";

const NOW = new Date("2026-11-01T02:00:00Z");
const FALLBACK = { place: "已選地點", custom: "自訂地點", device: "目前位置" };

const saved: Conditions = {
  schema_version: 1,
  date: "2026-11-05",
  depart_time: "09:00",
  return_time: "17:00",
  start: { type: "place_ref", place_id: "0190a000-0000-7000-8000-000000000001" },
  end: null,
  travel_mode: "drive",
  children_ages: [4, 7],
  nap: null,
  lunch: { start: "11:30", end: "13:00" },
  dinner: null,
  rain_indoor_only: true,
  facility_prefs: ["nursing_room"],
  type_prefs: ["museum", "zoo"],
};

describe("recheckBlock", () => {
  test("出發時間未過且在今天起 7 天內才可重新檢查", () => {
    expect(recheckBlock({ date: "2026-11-01", depart_time: "10:15" }, NOW)).toBeNull();
    expect(recheckBlock({ date: "2026-11-07", depart_time: "09:00" }, NOW)).toBeNull();
  });

  test("出發時間已過（含同日較早時間）或超出第 6 天時不可", () => {
    expect(recheckBlock({ date: "2026-11-01", depart_time: "10:00" }, NOW)).toBe("DEPARTURE_PASSED");
    expect(recheckBlock({ date: "2026-10-30", depart_time: "09:00" }, NOW)).toBe("DEPARTURE_PASSED");
    expect(recheckBlock({ date: "2026-11-08", depart_time: "09:00" }, NOW)).toBe("OUTSIDE_EXTERNAL_COVERAGE");
  });
});

describe("conditionsToForm", () => {
  test("沿用條件，轉回表單後送出的條件與原本相同", () => {
    const f = conditionsToForm(saved, { start: "兒童探索博物館", end: null }, NOW);
    expect(f.start?.display).toBe("兒童探索博物館");
    expect(f.endSame).toBe(true);
    expect(f.lunch.enabled).toBe(true);
    expect(f.nap.enabled).toBe(false);
    expect(toConditions(f)).toEqual({ ...saved, nap: null, dinner: null, end: null });
  });

  test("原日期已不在可選範圍時改用預設日期（明天），其他沿用", () => {
    const f = conditionsToForm({ ...saved, date: "2026-10-20" }, { start: "兒童探索博物館", end: null }, NOW);
    expect(f.date).toBe("2026-11-02");
    expect(f.children).toEqual([4, 7]);
  });

  test("終點不同時保留終點與其顯示名稱", () => {
    const end = { type: "device_coordinate" as const, lat: 25.03, lng: 121.56, accuracy_m: 20, label: null };
    const f = conditionsToForm({ ...saved, end }, { start: "兒童探索博物館", end: "目前位置" }, NOW);
    expect(f.endSame).toBe(false);
    expect(f.end).toEqual({ endpoint: end, display: "目前位置" });
  });
});

describe("endpointName", () => {
  test("本專案地點用開放資料名稱，其他用自填標籤，都沒有時用通用文字", () => {
    const ref = { type: "place_ref" as const, place_id: "0190a000-0000-7000-8000-000000000001" };
    expect(endpointName(ref, "兒童探索博物館", null, FALLBACK)).toBe("兒童探索博物館");
    expect(endpointName(ref, null, null, FALLBACK)).toBe("已選地點");
    const home = { type: "google_place" as const, google_place_id: "ChIJhome", endpoint_id: null, label: null };
    expect(endpointName(home, null, "家", FALLBACK)).toBe("家");
    expect(endpointName(home, null, null, FALLBACK)).toBe("自訂地點");
    const dev = { type: "device_coordinate" as const, lat: 25.03, lng: 121.56, accuracy_m: 20, label: null };
    expect(endpointName(dev, null, null, FALLBACK)).toBe("目前位置");
  });
});
