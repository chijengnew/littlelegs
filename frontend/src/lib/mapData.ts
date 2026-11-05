import type { CandidateResponse, PlanResponse, Schemas } from "./api/client";

export type LatLng = { lat: number; lng: number };

export type MapPoint = LatLng & {
  key: string;
  kind: "start" | "end" | "start_end" | "stop" | "candidate";
  glyph: string;
  title: string;
  selected?: boolean;
};

export type MapScene = { points: MapPoint[]; path: LatLng[] | null };

export type EndpointTitles = { start: string; end: string; startEnd: string };

type Located = { location?: Schemas["Location"] | null };

function at(x: Located | null | undefined): LatLng | null {
  const l = x?.location;
  return l && Number.isFinite(l.lat) && Number.isFinite(l.lng) ? { lat: l.lat, lng: l.lng } : null;
}

const same = (a: LatLng, b: LatLng) => a.lat === b.lat && a.lng === b.lng;

function endpointPoints(start: Located, end: Located, titles: EndpointTitles): MapPoint[] {
  const s = at(start);
  const e = at(end);
  if (s && e && same(s, e)) return [{ key: "start", kind: "start_end", glyph: "起終", title: titles.startEnd, ...s }];
  const out: MapPoint[] = [];
  if (s) out.push({ key: "start", kind: "start", glyph: "起", title: titles.start, ...s });
  if (e) out.push({ key: "end", kind: "end", glyph: "終", title: titles.end, ...e });
  return out;
}

export function candidateScene(
  resp: Pick<CandidateResponse, "start" | "end" | "candidates">,
  selectedIds: readonly string[],
  titles: EndpointTitles,
): MapScene {
  const chosen = new Set(selectedIds);
  const points = endpointPoints(resp.start, resp.end, titles);
  for (const c of resp.candidates) {
    const p = at(c);
    if (p) points.push({ key: c.place_id, kind: "candidate", glyph: "", title: c.name, selected: chosen.has(c.place_id), ...p });
  }
  return { points, path: null };
}

export function planScene(
  plan: Pick<PlanResponse, "start" | "end" | "stops">,
  order: readonly string[],
  titles: EndpointTitles,
): MapScene {
  const byId = new Map(plan.stops.map((s) => [s.place_id, s]));
  const stops: MapPoint[] = [];
  order.forEach((id, i) => {
    const s = byId.get(id);
    const p = at(s);
    if (s && p) stops.push({ key: id, kind: "stop", glyph: String(i + 1), title: `${i + 1}. ${s.name}`, ...p });
  });
  const ends = endpointPoints(plan.start, plan.end, titles);
  let path: LatLng[] | null = null;
  if (order.length >= 2 && stops.length === order.length) {
    const s = at(plan.start);
    const e = at(plan.end);
    path = [...(s ? [s] : []), ...stops.map(({ lat, lng }) => ({ lat, lng })), ...(e ? [e] : [])];
  }
  return { points: [...ends, ...stops], path };
}

type SavedLike = {
  start_location?: Schemas["Location"] | null;
  end_location?: Schemas["Location"] | null;
  stops?: { place_id: string; name?: string | null; location?: Schemas["Location"] | null }[] | null;
};

export function savedScene(item: SavedLike, titles: EndpointTitles, unknownName: string): MapScene & { missingEndpoint: boolean } {
  const stops = item.stops ?? [];
  const order = stops.map((s) => s.place_id);
  const plan = {
    start: { location: item.start_location },
    end: { location: item.end_location },
    stops: stops.map((s) => ({ place_id: s.place_id, name: s.name ?? unknownName, location: s.location })),
  } as Pick<PlanResponse, "start" | "end" | "stops">;
  const scene = planScene(plan, order, titles);
  return { ...scene, missingEndpoint: stops.length > 0 && (!item.start_location || !item.end_location) };
}

export function boundsOf(points: readonly LatLng[]): { north: number; south: number; east: number; west: number } | null {
  if (points.length === 0) return null;
  let north = -90, south = 90, east = -180, west = 180;
  for (const { lat, lng } of points) {
    north = Math.max(north, lat);
    south = Math.min(south, lat);
    east = Math.max(east, lng);
    west = Math.min(west, lng);
  }
  return { north, south, east, west };
}
