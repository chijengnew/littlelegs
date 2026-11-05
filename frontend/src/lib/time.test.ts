import { describe, expect, test } from "vitest";
import { QUARTER_TIMES, addDays, dateRange, formatClock, fromMinutes, taipeiInstant, taipeiToday, toMinutes } from "./time";

describe("台北日期", () => {
  test("UTC 16:00 起算台北隔天", () => {
    expect(taipeiToday(new Date("2026-10-28T15:59:59Z"))).toBe("2026-10-28");
    expect(taipeiToday(new Date("2026-10-28T16:00:00Z"))).toBe("2026-10-29");
  });

  test("addDays 跨月、跨年", () => {
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDays("2027-02-28", 1)).toBe("2027-03-01");
  });

  test("可選日期為 D 至 D+29", () => {
    expect(dateRange(new Date("2026-10-29T02:00:00Z"))).toEqual({ min: "2026-10-29", max: "2026-11-27" });
  });

  test("台北當地時間轉 UTC 時間點", () => {
    expect(taipeiInstant("2026-10-30", "09:00").toISOString()).toBe("2026-10-30T01:00:00.000Z");
  });
});

describe("15 分鐘刻度", () => {
  test("分鐘互轉", () => {
    expect(toMinutes("13:45")).toBe(825);
    expect(fromMinutes(825)).toBe("13:45");
  });

  test("一天 96 個刻度", () => {
    expect(QUARTER_TIMES).toHaveLength(96);
    expect(QUARTER_TIMES[0]).toBe("00:00");
    expect(QUARTER_TIMES.at(-1)).toBe("23:45");
  });
});

describe("formatClock", () => {
  test("ISO 時間點顯示為台北 HH:MM", () => {
    expect(formatClock("2026-10-30T01:00:00Z")).toBe("09:00");
  });

  test("缺值與無法辨識的值", () => {
    expect(formatClock(null)).toBe("--:--");
    expect(formatClock("not-a-time")).toBe("not-a-time");
  });
});
