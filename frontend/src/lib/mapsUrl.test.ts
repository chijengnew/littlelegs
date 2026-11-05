import { describe, expect, test } from "vitest";
import { endpointTarget, navigationUrl, placeTarget, planLegUrl, routeUrl, type NavTarget } from "./mapsUrl";

const params = (url: string | null) => new URL(url ?? "").searchParams;
const target = (query: string, placeId: string | null = null): NavTarget => ({ query, placeId });

describe("目的地", () => {
  test("本專案地點：有可靠 Place ID 時用名稱＋ID", () => {
    expect(placeTarget({ name: "動物園", address: "臺北市", google_place_id: "ChIJa" })).toEqual(target("動物園", "ChIJa"));
  });

  test("本專案地點：沒有可靠 ID 時改用名稱＋地址，不猜 ID", () => {
    expect(placeTarget({ name: "某飯店", address: "臺南市中西區", google_place_id: null })).toEqual(target("某飯店 臺南市中西區"));
    expect(placeTarget({ name: "某飯店" })).toEqual(target("某飯店"));
  });

  test("已下架或沒有名稱的地點不提供導航", () => {
    expect(placeTarget({ name: "舊景點", google_place_id: "ChIJa", removed: true })).toBeNull();
    expect(placeTarget({ name: null })).toBeNull();
    expect(placeTarget(undefined)).toBeNull();
  });

  test("Google 地點選取：Place ID 搭配目的地文字，沒有標籤時用預設文字", () => {
    expect(endpointTarget({ type: "google_place", google_place_id: "ChIJh", label: "家" }, "目的地")).toEqual(target("家", "ChIJh"));
    expect(endpointTarget({ type: "google_place", google_place_id: "ChIJh" }, "目的地")).toEqual(target("目的地", "ChIJh"));
    expect(endpointTarget({ type: "google_place" }, "目的地")).toBeNull();
  });

  test("裝置座標：latitude,longitude", () => {
    expect(endpointTarget({ type: "device_coordinate", coordinate: { lat: 25.033, lng: 121.5654 } }, "目的地")).toEqual(target("25.033,121.5654"));
    expect(endpointTarget({ type: "device_coordinate" }, "目的地")).toBeNull();
  });
});

describe("導航連結", () => {
  test("單一目的地：開車、導航模式、不帶起點", () => {
    const url = navigationUrl(target("臺北市立動物園", "ChIJa"));
    expect(url.startsWith("https://www.google.com/maps/dir/?")).toBe(true);
    const q = params(url);
    expect(q.get("api")).toBe("1");
    expect(q.get("destination")).toBe("臺北市立動物園");
    expect(q.get("destination_place_id")).toBe("ChIJa");
    expect(q.get("travelmode")).toBe("driving");
    expect(q.get("dir_action")).toBe("navigate");
    expect(q.has("origin")).toBe(false);
  });

  test("沒有 Place ID 時不送 destination_place_id", () => {
    expect(params(navigationUrl(target("25.033,121.5654"))).has("destination_place_id")).toBe(false);
  });

  test("時間軸各段對應起點、終點或景點", () => {
    const plan = {
      start: { type: "google_place" as const, google_place_id: "ChIJh", label: "家" },
      end: { type: "device_coordinate" as const, coordinate: { lat: 25, lng: 121 } },
      stops: [{ place_id: "p1", name: "動物園", google_place_id: "ChIJa", stay_minutes: 60, stay_source: "user" as const, estimated: false, hours: null, removed: false }],
    };
    expect(params(planLegUrl(plan, "p1", "目的地")).get("destination_place_id")).toBe("ChIJa");
    expect(params(planLegUrl(plan, "start", "目的地")).get("destination_place_id")).toBe("ChIJh");
    expect(params(planLegUrl(plan, "end", "目的地")).get("destination")).toBe("25,121");
    expect(planLegUrl(plan, "?", "目的地")).toBeNull();
    expect(planLegUrl(plan, null, "目的地")).toBeNull();
  });
});

describe("全程路線", () => {
  const stops = [target("A", "ChIJa"), target("B", "ChIJb"), target("C", "ChIJc")];

  test("中途點與 Place ID 依序對應，只是路線預覽", () => {
    const q = params(routeUrl(stops, target("家", "ChIJh")));
    expect(q.get("waypoints")).toBe("A|B|C");
    expect(q.get("waypoint_place_ids")).toBe("ChIJa|ChIJb|ChIJc");
    expect(q.get("destination_place_id")).toBe("ChIJh");
    expect(q.has("dir_action")).toBe(false);
  });

  test("有任一站沒有 ID 時，全部不帶 waypoint_place_ids", () => {
    expect(params(routeUrl([target("A", "ChIJa"), target("B")], target("家"))).has("waypoint_place_ids")).toBe(false);
  });

  test("超過 3 個中途點、任一站不可導航或沒有終點時不提供", () => {
    expect(routeUrl([...stops, target("D", "ChIJd")], target("家"))).toBeNull();
    expect(routeUrl([stops[0], null], target("家"))).toBeNull();
    expect(routeUrl(stops, null)).toBeNull();
    expect(routeUrl([], target("家"))).toBeNull();
  });
});
