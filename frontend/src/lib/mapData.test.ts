import { describe, expect, test } from "vitest";
import type { Schemas } from "./api/client";
import { boundsOf, candidateScene, planScene, savedScene } from "./mapData";

const TITLES = { start: "起點", end: "終點", startEnd: "起點（終點同起點）" };
const loc = (lat: number, lng: number): Schemas["Location"] => ({ lat, lng, source: "open_data" });
const ep = (location: Schemas["Location"] | null): Schemas["EndpointOut"] => ({ type: "place_ref", place_id: "s", location });
const stop = (place_id: string, name: string, location: Schemas["Location"] | null) =>
  ({ place_id, name, location }) as Schemas["PlanStopOut"];
const cand = (place_id: string, name: string, location: Schemas["Location"] | null) =>
  ({ place_id, name, location }) as Schemas["CandidateOut"];

const HOME = loc(25.03, 121.56);
const A = stop("a", "博物館", loc(25.04, 121.52));
const B = stop("b", "親子館", loc(25.06, 121.55));
const C = stop("c", "公園", loc(25.01, 121.5));

describe("planScene", () => {
  test("只選 1 個景點：只標位置、不連線", () => {
    const sc = planScene({ start: ep(HOME), end: ep(HOME), stops: [A] }, ["a"], TITLES);
    expect(sc.path).toBeNull();
    expect(sc.points.map((p) => [p.kind, p.glyph])).toEqual([["start_end", "起終"], ["stop", "1"]]);
  });

  test("2 個以上依採用順序連線：起點 → 景點 → 終點（起訖相同時回到起點）", () => {
    const sc = planScene({ start: ep(HOME), end: ep(HOME), stops: [A, B, C] }, ["c", "a", "b"], TITLES);
    expect(sc.points.filter((p) => p.kind === "stop").map((p) => [p.key, p.glyph, p.title])).toEqual([
      ["c", "1", "1. 公園"],
      ["a", "2", "2. 博物館"],
      ["b", "3", "3. 親子館"],
    ]);
    expect(sc.path).toEqual([
      { lat: 25.03, lng: 121.56 },
      { lat: 25.01, lng: 121.5 },
      { lat: 25.04, lng: 121.52 },
      { lat: 25.06, lng: 121.55 },
      { lat: 25.03, lng: 121.56 },
    ]);
  });

  test("起訖不同：分別標「起」「終」，連線終於終點", () => {
    const END = loc(24.99, 121.3);
    const sc = planScene({ start: ep(HOME), end: ep(END), stops: [A, B] }, ["a", "b"], TITLES);
    expect(sc.points.slice(0, 2).map((p) => [p.kind, p.glyph])).toEqual([["start", "起"], ["end", "終"]]);
    expect(sc.path?.at(-1)).toEqual({ lat: 24.99, lng: 121.3 });
  });

  test("調整後尚未檢查：依畫面順序；移除的景點不畫；上次回應沒有的景點不畫也不連線", () => {
    expect(planScene({ start: ep(HOME), end: ep(HOME), stops: [A, B, C] }, ["b", "a"], TITLES).points.map((p) => p.key))
      .toEqual(["start", "b", "a"]);
    const sc = planScene({ start: ep(HOME), end: ep(HOME), stops: [A] }, ["a", "x"], TITLES);
    expect(sc.points.map((p) => p.key)).toEqual(["start", "a"]);
    expect(sc.path).toBeNull();
  });

  test("訪客回應（沒有座標）：沒有任何點", () => {
    const sc = planScene({ start: ep(null), end: ep(null), stops: [stop("a", "博物館", null)] }, ["a"], TITLES);
    expect(sc).toEqual({ points: [], path: null });
  });
});

describe("candidateScene", () => {
  test("起訖點＋有座標的候選，標示已勾選者，不連線", () => {
    const sc = candidateScene(
      { start: ep(HOME), end: ep(HOME), candidates: [cand("a", "博物館", loc(25.04, 121.52)), cand("b", "親子館", null)] },
      ["a"],
      TITLES,
    );
    expect(sc.path).toBeNull();
    expect(sc.points.map((p) => [p.key, p.kind, !!p.selected])).toEqual([
      ["start", "start_end", false],
      ["a", "candidate", true],
    ]);
  });
});

describe("boundsOf", () => {
  test("涵蓋所有點；沒有點時為 null", () => {
    expect(boundsOf([])).toBeNull();
    expect(boundsOf([{ lat: 25, lng: 121.5 }, { lat: 24.9, lng: 121.6 }])).toEqual({ north: 25, south: 24.9, east: 121.6, west: 121.5 });
  });
});

describe("savedScene（詳細頁，開啟時不呼叫 Google）", () => {
  const stopsSaved = [
    { place_id: "a", name: "博物館", location: loc(25.04, 121.52) },
    { place_id: "b", name: null, location: loc(25.06, 121.55) },
  ];

  test("本專案地點或裝置座標的起訖點：完整標示並依保存的順序連線", () => {
    const sc = savedScene({ start_location: HOME, end_location: HOME, stops: stopsSaved }, TITLES, "已不存在的地點");
    expect(sc.missingEndpoint).toBe(false);
    expect(sc.points.map((p) => [p.kind, p.glyph, p.title])).toEqual([
      ["start_end", "起終", "起點（終點同起點）"],
      ["stop", "1", "1. 博物館"],
      ["stop", "2", "2. 已不存在的地點"],
    ]);
    expect(sc.path).toHaveLength(4);
  });

  test("起點是 Google 地點（座標不保存）：不標起點，連線只連景點與有座標的終點", () => {
    const END = loc(24.99, 121.3);
    const sc = savedScene({ start_location: null, end_location: END, stops: stopsSaved }, TITLES, "?");
    expect(sc.missingEndpoint).toBe(true);
    expect(sc.points.map((p) => p.kind)).toEqual(["end", "stop", "stop"]);
    expect(sc.path).toEqual([{ lat: 25.04, lng: 121.52 }, { lat: 25.06, lng: 121.55 }, { lat: 24.99, lng: 121.3 }]);
  });

  test("起訖都是 Google 地點：只標景點；沒有景點時不算缺起訖點", () => {
    const sc = savedScene({ start_location: null, end_location: null, stops: stopsSaved }, TITLES, "?");
    expect(sc.points.map((p) => p.kind)).toEqual(["stop", "stop"]);
    expect(sc.path).toEqual([{ lat: 25.04, lng: 121.52 }, { lat: 25.06, lng: 121.55 }]);
    expect(savedScene({ start_location: null, end_location: null, stops: [] }, TITLES, "?").missingEndpoint).toBe(false);
  });
});
