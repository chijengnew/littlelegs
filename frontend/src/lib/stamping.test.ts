import { describe, expect, test, vi } from "vitest";
import zh from "../../messages/zh-TW.json";
import {
  GEO_OPTIONS,
  GeoError,
  dateLines,
  failureKey,
  geoFailure,
  geoKey,
  locate,
  manualAllowed,
  newAttempt,
  stampDay,
  taipeiDay,
  uncertain,
} from "./stamping";

const PLACE = "0190a000-0000-7000-8000-000000000002";
const err = (status: number, code = "X") => ({ code, status, message: "", fieldErrors: [] });

function lookup(path: string): unknown {
  return path.split(".").reduce<unknown>((o, k) => (o && typeof o === "object" ? (o as Record<string, unknown>)[k] : undefined), zh);
}

describe("蓋章請求與 key 生命週期", () => {
  test("定位核對帶本次座標，手動紀錄不帶位置；每次嘗試都是新的 UUIDv7 key", () => {
    const a = newAttempt(PLACE, { lat: 25.03, lng: 121.53, accuracy_m: 12 });
    const b = newAttempt(PLACE, { lat: 25.03, lng: 121.53, accuracy_m: 12 });
    const m = newAttempt(PLACE, null);
    expect(a.body).toEqual({ place_id: PLACE, verification_method: "location", location: { lat: 25.03, lng: 121.53, accuracy_m: 12 } });
    expect(m.body).toEqual({ place_id: PLACE, verification_method: "manual" });
    expect(a.key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(new Set([a.key, b.key, m.key]).size).toBe(3);
  });

  test("只有結果不確定（離線或伺服器錯誤）才用原 key 重送；明確失敗要重新開始", () => {
    expect(uncertain(err(0, "NETWORK"))).toBe(true);
    expect(uncertain(err(503))).toBe(true);
    expect(uncertain(err(500))).toBe(true);
    for (const s of [401, 403, 404, 409, 422, 429]) expect(uncertain(err(s))).toBe(false);
  });

  test("不能蓋章的景點不提供手動紀錄，定位失敗仍可手動", () => {
    for (const c of ["PLACE_REMOVED", "PLACE_NOT_STAMPABLE", "PLACE_NO_COORDINATES", "PLACE_NOT_FOUND"]) expect(manualAllowed(c)).toBe(false);
    for (const c of ["LOCATION_TOO_FAR", "LOCATION_INACCURATE", "NETWORK", "RATE_LIMITED"]) expect(manualAllowed(c)).toBe(true);
  });

  test("已知錯誤代碼都有對應文案", () => {
    for (const c of ["LOCATION_TOO_FAR", "LOCATION_INACCURATE", "PLACE_REMOVED", "PLACE_NOT_STAMPABLE", "PLACE_NO_COORDINATES", "PLACE_NOT_FOUND", "NETWORK"]) {
      const key = failureKey(c);
      expect(key).not.toBeNull();
      expect(typeof lookup(key!)).toBe("string");
    }
    expect(failureKey("SOMETHING_ELSE")).toBeNull();
    for (const r of ["denied", "unavailable", "timeout", "unsupported"] as const) expect(typeof lookup(geoKey(r))).toBe("string");
  });
});

describe("瀏覽器定位", () => {
  test("使用高精確度、20 秒逾時、不接受快取位置", () => {
    expect(GEO_OPTIONS).toEqual({ enableHighAccuracy: true, timeout: 20000, maximumAge: 0 });
  });

  test("成功時只取經緯度與精確度", async () => {
    const geo = {
      getCurrentPosition: vi.fn((ok: PositionCallback, _fail: PositionErrorCallback, opts?: PositionOptions) => {
        expect(opts).toEqual(GEO_OPTIONS);
        ok({ coords: { latitude: 25.03, longitude: 121.53, accuracy: 18, altitude: 3 }, timestamp: 1 } as unknown as GeolocationPosition);
      }),
    } as unknown as Geolocation;
    await expect(locate(geo)).resolves.toEqual({ lat: 25.03, lng: 121.53, accuracy_m: 18 });
  });

  test("拒絕、逾時、取不到與不支援分別回報", async () => {
    expect([geoFailure(1), geoFailure(2), geoFailure(3)]).toEqual(["denied", "unavailable", "timeout"]);
    const geo = {
      getCurrentPosition: (_ok: PositionCallback, fail: PositionErrorCallback) => fail({ code: 1 } as GeolocationPositionError),
    } as unknown as Geolocation;
    await expect(locate(geo)).rejects.toEqual(new GeoError("denied"));
    await expect(locate(undefined)).rejects.toMatchObject({ reason: "unsupported" });
  });
});

describe("日期標示", () => {
  const visited = "2026-11-12T16:30:00+00:00";
  const later = "2026-11-14T03:00:00+00:00";

  test("台北日期換算", () => {
    expect(taipeiDay(visited)).toBe("2026-11-13");
    expect(taipeiDay("2026-11-12T15:59:59+00:00")).toBe("2026-11-12");
  });

  test("只有手動紀錄：紀錄日期", () => {
    expect(dateLines({ verification_method: "manual", visited_at: visited, verified_at: null })).toEqual([{ key: "recorded", at: visited }]);
  });

  test("直接定位核對：只顯示定位核對日期", () => {
    expect(dateLines({ verification_method: "location", visited_at: visited, verified_at: visited })).toEqual([{ key: "verified", at: visited }]);
  });

  test("先手動後定位：初次紀錄日期與定位核對日期分開，不把手動時間標成核對", () => {
    expect(dateLines({ verification_method: "location", visited_at: visited, verified_at: later })).toEqual([
      { key: "firstRecorded", at: visited },
      { key: "verified", at: later },
    ]);
    expect(stampDay({ verification_method: "location", visited_at: visited, verified_at: later })).toBe("2026-11-14");
    expect(stampDay({ verification_method: "manual", visited_at: visited, verified_at: null })).toBe("2026-11-13");
  });

  test("日期標籤都有文案", () => {
    for (const k of ["recorded", "firstRecorded", "verified"]) expect(typeof lookup(`explore.date.${k}`)).toBe("string");
  });
});
