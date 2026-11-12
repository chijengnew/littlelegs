import { describe, expect, test } from "vitest";
import type { Schemas } from "./api/client";
import { tripMax, tripParts } from "./weather";

const weather = (parts: Schemas["WeatherPartOut"][]): Schemas["WeatherOut"] => ({
  status: "not_triggered",
  max_precipitation_percent: 30,
  threshold_percent: 60,
  location: "start",
  note: null,
  explanation: "",
  source: "google",
  uncovered: [],
  rain_filter: false,
  areas: [],
  parts,
});

const day = { label: "日間", start: "2026-11-13T07:00:00+08:00", end: "2026-11-13T19:00:00+08:00", percent: 30, type: "RAIN" };
const night = { label: "夜間", start: "2026-11-13T19:00:00+08:00", end: "2026-11-14T07:00:00+08:00", percent: 70, type: "RAIN" };

describe("tripParts", () => {
  test("只留下和出遊時間重疊的時段，並裁成實際出遊的起訖時間", () => {
    expect(tripParts(weather([night, day]), "2026-11-13", "09:00", "17:00")).toEqual([
      { label: "日間", from: "09:00", to: "17:00", percent: 30 },
    ]);
  });

  test("回程晚於 19:00 時，日間和夜間依時間先後列出", () => {
    expect(tripParts(weather([night, day]), "2026-11-13", "10:00", "21:30")).toEqual([
      { label: "日間", from: "10:00", to: "19:00", percent: 30 },
      { label: "夜間", from: "19:00", to: "21:30", percent: 70 },
    ]);
  });

  test("沒有時間的時段略過，沒有預報數字時保留為 null", () => {
    const blank = { ...day, percent: null };
    expect(tripParts(weather([{ ...night, start: null }, blank]), "2026-11-13", "09:00", "17:00")).toEqual([
      { label: "日間", from: "09:00", to: "17:00", percent: null },
    ]);
  });
});

describe("tripMax", () => {
  test("只取出遊時段內的最高降水機率；完全沒有數字時回傳 null", () => {
    expect(tripMax({ parts: [night, day] }, "2026-11-13", "09:00", "17:00")).toBe(30);
    expect(tripMax({ parts: [night, day] }, "2026-11-13", "10:00", "21:30")).toBe(70);
    expect(tripMax({ parts: [{ ...day, percent: null }] }, "2026-11-13", "09:00", "17:00")).toBeNull();
  });
});
