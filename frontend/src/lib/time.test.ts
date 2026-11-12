import { describe, expect, test } from "vitest";
import { HALF_HOUR_TIMES, addDays, dateRange, formatClock, formatMonthDay, fromMinutes, taipeiInstant, taipeiToday, timeOptions, toMinutes } from "./time";

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

  test("選單一天 48 個半小時刻度", () => {
    expect(HALF_HOUR_TIMES).toHaveLength(48);
    expect(HALF_HOUR_TIMES[0]).toBe("00:00");
    expect(HALF_HOUR_TIMES[1]).toBe("00:30");
    expect(HALF_HOUR_TIMES.at(-1)).toBe("23:30");
  });

  test("舊的 15 分鐘值仍會出現在選單裡", () => {
    expect(timeOptions("09:00")).toBe(HALF_HOUR_TIMES);
    const opts = timeOptions("09:15");
    expect(opts).toHaveLength(49);
    expect(opts.slice(18, 21)).toEqual(["09:00", "09:15", "09:30"]);
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

test("標籤與摘要用的日期：11/13（五），月日不補零", () => {
  expect(formatMonthDay("2026-11-13")).toBe("11/13（五）");
  expect(formatMonthDay("2026-12-05")).toBe("12/5（六）");
});
