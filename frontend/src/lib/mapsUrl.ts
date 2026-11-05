import type { PlanResponse, Schemas } from "./api/client";

const DIRECTIONS = "https://www.google.com/maps/dir/";
export const MAX_ROUTE_WAYPOINTS = 3;

export type NavTarget = { query: string; placeId: string | null };

type PlaceLike = {
  name?: string | null;
  address?: string | null;
  google_place_id?: string | null;
  removed?: boolean | null;
};

export function placeTarget(p: PlaceLike | null | undefined): NavTarget | null {
  const name = p?.name?.trim();
  if (!p || p.removed || !name) return null;
  if (p.google_place_id) return { query: name, placeId: p.google_place_id };
  const address = p.address?.trim();
  return { query: address ? `${name} ${address}` : name, placeId: null };
}

export function endpointTarget(ep: Schemas["EndpointOut"] | null | undefined, fallbackLabel: string): NavTarget | null {
  if (!ep) return null;
  if (ep.type === "place_ref") return placeTarget(ep);
  if (ep.type === "google_place") {
    return ep.google_place_id ? { query: ep.label || fallbackLabel, placeId: ep.google_place_id } : null;
  }
  return ep.coordinate ? { query: `${ep.coordinate.lat},${ep.coordinate.lng}`, placeId: null } : null;
}

function directions(destination: NavTarget): URLSearchParams {
  const q = new URLSearchParams({ api: "1", destination: destination.query, travelmode: "driving" });
  if (destination.placeId) q.set("destination_place_id", destination.placeId);
  return q;
}

export function navigationUrl(destination: NavTarget): string {
  const q = directions(destination);
  q.set("dir_action", "navigate");
  return `${DIRECTIONS}?${q}`;
}

export function routeUrl(stops: (NavTarget | null)[], end: NavTarget | null): string | null {
  if (!end || stops.length === 0 || stops.length > MAX_ROUTE_WAYPOINTS) return null;
  const known = stops.filter((x): x is NavTarget => x !== null);
  if (known.length !== stops.length) return null;
  const q = directions(end);
  q.set("waypoints", known.map((x) => x.query.replaceAll("|", " ")).join("|"));
  if (known.every((x) => x.placeId)) q.set("waypoint_place_ids", known.map((x) => x.placeId).join("|"));
  return `${DIRECTIONS}?${q}`;
}

export function planLegUrl(
  plan: Pick<PlanResponse, "start" | "end" | "stops">,
  to: string | null | undefined,
  fallbackLabel: string,
): string | null {
  const target =
    to === "start"
      ? endpointTarget(plan.start, fallbackLabel)
      : to === "end"
        ? endpointTarget(plan.end, fallbackLabel)
        : placeTarget(plan.stops.find((x) => x.place_id === to));
  return target ? navigationUrl(target) : null;
}
