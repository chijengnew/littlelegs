import type { Page, Request } from "@playwright/test";
import type { components } from "../src/lib/api/schema";

type S = components["schemas"];

export const E2E_PORT = 3100;
export const E2E_API = `http://localhost:${E2E_PORT}/e2e-api`;

export const START: S["PlaceSummary"] = {
  place_id: "0190a000-0000-7000-8000-000000000001",
  kind: "attraction",
  name: "測試公園",
  address: "臺北市中正區測試路1號",
  city: "臺北市",
  primary_type: "park_playground",
};

const candidate = (place_id: string, name: string, primary_type: string, distance_m: number): S["CandidateOut"] => ({
  place_id,
  google_place_id: null,
  name,
  address: null,
  city: "臺北市",
  distance_m,
  distance_note: "起點直線距離，非開車距離",
  primary_type,
  types: { [primary_type]: "confirmed" },
  indoor: { value: "indoor", confirmation: "inferred" },
  facilities: {},
  age: "unknown",
  default_stay: { minutes: 90, source: "type_default", estimated: true },
  reasons: [{ code: "nearby", message: "距離起點較近" }],
  warnings: [],
});

export const MUSEUM = candidate("0190a000-0000-7000-8000-000000000002", "測試博物館", "museum", 1200);
export const CENTER = candidate("0190a000-0000-7000-8000-000000000003", "測試親子館", "parent_child_center", 2500);

const endpoint: S["EndpointOut"] = { type: "place_ref", place_id: START.place_id, location: null };
const lockedMap: S["MapHints"] = { mode: "locked_illustration", message: "登入後可查看地圖", connect_line: null, line_note: null };

export function candidateResponse(queryId: string): S["CandidateResponse"] {
  return {
    query_id: queryId,
    operation: "ok",
    start: endpoint,
    end: endpoint,
    weather: null,
    candidates: [MUSEUM, CENTER],
    candidate_count: 2,
    lodging: { empty: true, items: [], note: null },
    history: null,
    map: lockedMap,
    field_sources: {},
    attributions: [],
    notices: ["營業時間會在排序或檢查行程時確認"],
  };
}

type StopIn = { place_id: string; stay_minutes: number | null };
const NAMES: Record<string, string> = { [MUSEUM.place_id]: MUSEUM.name, [CENTER.place_id]: CENTER.name };

export function planResponse(queryId: string, mode: "auto" | "manual", stops: StopIn[]): S["PlanResponse"] {
  const order = stops.map((x) => x.place_id);
  return {
    query_id: queryId,
    mode,
    operation: "ok",
    feasibility: "unverified",
    feasibility_note: "沒有已知違反，但必要資料缺漏或涵蓋不足",
    order,
    stops: stops.map((x) => ({
      place_id: x.place_id,
      name: NAMES[x.place_id],
      google_place_id: `ChIJ${x.place_id.slice(-4)}`,
      primary_type: x.place_id === MUSEUM.place_id ? "museum" : "parent_child_center",
      stay_minutes: x.stay_minutes ?? 90,
      stay_source: x.stay_minutes === null ? "type_default" : "user",
      estimated: x.stay_minutes === null,
      hours: null,
      removed: false,
    })),
    timeline: [
      { type: "move", start: "2026-10-30T01:00:00Z", end: "2026-10-30T01:12:00Z", estimated: true, source: "google", from: "start", to: order[0], duration_s: 700, distance_m: 4200 },
      { type: "attraction", start: "2026-10-30T01:30:00Z", end: "2026-10-30T03:00:00Z", estimated: true, source: "system", place_id: order[0], name: NAMES[order[0]] },
    ],
    warnings: [],
    violation_codes: [],
    violations: [],
    suggest_remove: [],
    search: { complete: true, optimal_claimed: mode === "auto", permutations_evaluated: mode === "auto" ? 2 : 1, note: "" },
    start: endpoint,
    end: endpoint,
    weather: null,
    history: null,
    map: lockedMap,
    field_sources: {},
    attributions: [],
    notices: [],
  };
}

export type Call = { method: string; path: string; body: Record<string, unknown> | null };

const placeDetail: S["PlaceDetailResponse"] = {
  place: {
    place_id: MUSEUM.place_id,
    kind: "attraction",
    name: MUSEUM.name,
    address: "臺北市中正區測試路2號",
    city: "臺北市",
    location: null,
    primary_type: "museum",
    types: { museum: "confirmed" },
    indoor: { value: "indoor", confirmation: "inferred" },
    facilities: {},
    source_stay_minutes: null,
    removed: false,
    removed_note: null,
  },
  sources: [],
  evidence: { types: [], facilities: [], indoor: null, age_ranges: [], age_exclusions: [] },
};

export async function mockApi(page: Page, { delayMs = 0, feedbackLimit = 100 }: { delayMs?: number; feedbackLimit?: number } = {}) {
  const calls: Call[] = [];
  const unexpected: string[] = [];
  await page.route(`${E2E_API}/**`, async (route) => {
    const req: Request = route.request();
    const path = new URL(req.url()).pathname.replace(/^\/e2e-api/, "");
    const body = req.postData() ? (JSON.parse(req.postData()!) as Record<string, unknown>) : null;
    calls.push({ method: req.method(), path, body });
    if (delayMs) await new Promise((r) => setTimeout(r, delayMs));
    const json = (data: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data) });
    if (req.method() === "POST" && path === "/v1/endpoints/places/search") return json({ items: [START] });
    if (req.method() === "POST" && path === "/v1/trips/candidates") return json(candidateResponse(String(body?.query_id)));
    if (req.method() === "POST" && path === "/v1/trips/sort") {
      const stops = [...(body?.stops as StopIn[])].reverse();
      return json(planResponse(String(body?.query_id), "auto", stops));
    }
    if (req.method() === "POST" && path === "/v1/trips/check") {
      return json(planResponse(String(body?.query_id), "manual", body?.stops as StopIn[]));
    }
    if (req.method() === "GET" && path === `/v1/places/${MUSEUM.place_id}`) return json(placeDetail);
    if (req.method() === "POST" && path === "/v1/feedback") {
      const limited = calls.filter((c) => c.path === path).length > feedbackLimit;
      if (limited) {
        return route.fulfill({
          status: 429,
          contentType: "application/problem+json",
          body: JSON.stringify({ type: "about:blank", title: "Too Many Requests", status: 429, code: "RATE_LIMITED", detail: "請求過於頻繁" }),
        });
      }
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ status: "received" }) });
    }
    unexpected.push(`${req.method()} ${path}`);
    return route.fulfill({ status: 599, body: "unmocked" });
  });
  return { calls, unexpected, called: (path: string) => calls.filter((c) => c.path === path) };
}
