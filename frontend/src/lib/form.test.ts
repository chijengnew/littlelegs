import { describe, expect, test } from "vitest";
import {
  clampConditionStep, fieldFromLoc, firstStepWithError, initialForm, stepErrors, toConditions, validateForm, type FormState,
} from "./form";

const NOW = new Date("2026-10-29T02:00:00Z");

function valid(overrides: Partial<FormState> = {}): FormState {
  return {
    ...initialForm(NOW),
    start: { endpoint: { type: "place_ref", place_id: "0190a000-0000-7000-8000-000000000001" }, display: "測試公園" },
    endSame: true,
    children: [4],
    ...overrides,
  };
}

describe("validateForm", () => {
  test("「終點同起點」與午餐時段預設不勾；未勾終點同起點時須選終點", () => {
    const f = initialForm(NOW);
    expect(f.endSame).toBe(false);
    expect(f.lunch.enabled).toBe(false);
    expect(validateForm({ ...valid(), endSame: false }, NOW).end).toBe("validation.end");
  });

  test("預設為明天且填好必填即通過", () => {
    expect(initialForm(NOW).date).toBe("2026-10-30");
    expect(validateForm(valid(), NOW)).toEqual({});
  });

  test("日期只能 D 至 D+29", () => {
    expect(validateForm(valid({ date: "2026-10-28" }), NOW).date).toBe("validation.date");
    expect(validateForm(valid({ date: "2026-11-27" }), NOW).date).toBeUndefined();
    expect(validateForm(valid({ date: "2026-11-28" }), NOW).date).toBe("validation.date");
  });

  test("時間須為 15 分鐘刻度", () => {
    expect(validateForm(valid({ depart_time: "09:10" }), NOW).depart_time).toBe("validation.quarter");
  });

  test("回程至少比出發晚 120 分鐘", () => {
    expect(validateForm(valid({ return_time: "10:45", lunch: { enabled: false, start: "11:30", end: "13:00" } }), NOW).return_time)
      .toBe("validation.returnGap");
    expect(validateForm(valid({ return_time: "11:00", lunch: { enabled: false, start: "11:30", end: "13:00" } }), NOW).return_time)
      .toBeUndefined();
  });

  test("當天出發時間須晚於現在", () => {
    expect(validateForm(valid({ date: "2026-10-29", depart_time: "09:00" }), NOW).depart_time).toBe("validation.departPast");
    expect(validateForm(valid({ date: "2026-10-29", depart_time: "10:15" }), NOW).depart_time).toBeUndefined();
  });

  test("孩子 1–5 位、每位 0–18 歲且必填", () => {
    expect(validateForm(valid({ children: [null] }), NOW).children).toBe("validation.children");
    expect(validateForm(valid({ children: [0] }), NOW).children).toBeUndefined();
    expect(validateForm(valid({ children: [19] }), NOW).children).toBe("validation.children");
    expect(validateForm(valid({ children: [1, 2, 3, 4, 5, 6] }), NOW).children).toBe("validation.children");
  });

  test("起點必填；終點不同於起點時亦必填", () => {
    expect(validateForm(valid({ start: null }), NOW).start).toBe("validation.start");
    expect(validateForm(valid({ endSame: false, end: null }), NOW).end).toBe("validation.end");
  });

  test("午睡須開始早於結束且位於行程內", () => {
    expect(validateForm(valid({ nap: { enabled: true, start: "13:00", end: "13:00" } }), NOW).nap).toBe("validation.window");
    expect(validateForm(valid({ nap: { enabled: true, start: "08:00", end: "09:30" } }), NOW).nap).toBe("validation.window");
  });

  test("用餐時段至少 60 分鐘且位於行程內", () => {
    expect(validateForm(valid({ lunch: { enabled: true, start: "11:30", end: "12:15" } }), NOW).lunch).toBe("validation.meal");
    expect(validateForm(valid({ dinner: { enabled: true, start: "17:30", end: "19:00" } }), NOW).dinner).toBe("validation.meal");
  });
});

describe("toConditions", () => {
  test("終點同起點送 null、未啟用時段送 null、偏好排序", () => {
    const c = toConditions(valid({
      type_prefs: ["zoo", "museum"],
      facility_prefs: ["nursing_room", "family_toilet"],
      lunch: { enabled: true, start: "11:30", end: "13:00" },
    }));
    expect(c.end).toBeNull();
    expect(c.nap).toBeNull();
    expect(c.lunch).toEqual({ start: "11:30", end: "13:00" });
    expect(c.type_prefs).toEqual(["museum", "zoo"]);
    expect(c.facility_prefs).toEqual(["family_toilet", "nursing_room"]);
    expect(c.travel_mode).toBe("drive");
  });
});

describe("fieldFromLoc", () => {
  test("後端錯誤位置對應表單欄位", () => {
    expect(fieldFromLoc("conditions.depart_time")).toBe("depart_time");
    expect(fieldFromLoc("conditions.children_ages.0")).toBe("children");
    expect(fieldFromLoc("conditions")).toBe("return_time");
    expect(fieldFromLoc("stops.0")).toBeNull();
  });
});

describe("條件子步驟", () => {
  test("各子步驟只取自己的欄位錯誤", () => {
    const errors = { date: "a", start: "b", children: "c", lunch: "d" };
    expect(stepErrors(errors, 0)).toEqual({ date: "a" });
    expect(stepErrors(errors, 1)).toEqual({ start: "b" });
    expect(stepErrors(errors, 2)).toEqual({ children: "c" });
    expect(stepErrors(errors, 3)).toEqual({ lunch: "d" });
  });

  test("有錯誤時回到最前面需要修正的子步驟", () => {
    expect(firstStepWithError({})).toBe(-1);
    expect(firstStepWithError({ children: "x", nap: "y" })).toBe(2);
    expect(firstStepWithError({ end: "x", depart_time: "y" })).toBe(0);
  });

  test("暫存的子步驟只接受範圍內的整數", () => {
    expect(clampConditionStep(2)).toBe(2);
    expect(clampConditionStep(9)).toBe(3);
    expect(clampConditionStep(-1)).toBe(0);
    expect(clampConditionStep("2")).toBe(0);
    expect(clampConditionStep(1.5)).toBe(0);
    expect(clampConditionStep(undefined)).toBe(0);
  });
});
