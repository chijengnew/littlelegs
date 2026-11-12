import type { Schemas } from "./api/client";
import type { UiError } from "./api/problem";
import { uuidv7 } from "./ids";
import { TZ } from "./time";

export type CheckIn = Schemas["CheckInOut"];
export type CheckInBody = Schemas["CheckInIn"];
export type Fix = { lat: number; lng: number; accuracy_m: number };
export type Attempt = { key: string; body: CheckInBody };
export type GeoFailure = "denied" | "unavailable" | "timeout" | "unsupported";

export const GEO_OPTIONS: PositionOptions = { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 };

export function newAttempt(placeId: string, fix: Fix | null, now: number = Date.now()): Attempt {
  const body: CheckInBody = fix
    ? { place_id: placeId, verification_method: "location", location: { lat: fix.lat, lng: fix.lng, accuracy_m: fix.accuracy_m } }
    : { place_id: placeId, verification_method: "manual" };
  return { key: uuidv7(now), body };
}

export class GeoError extends Error {
  constructor(readonly reason: GeoFailure) {
    super(reason);
    this.name = "GeoError";
  }
}

export function geoFailure(code: number): GeoFailure {
  if (code === 1) return "denied";
  if (code === 3) return "timeout";
  return "unavailable";
}

export function locate(geo: Geolocation | undefined = typeof navigator === "undefined" ? undefined : navigator.geolocation): Promise<Fix> {
  if (!geo || (typeof window !== "undefined" && window.isSecureContext === false)) {
    return Promise.reject(new GeoError("unsupported"));
  }
  return new Promise((resolve, reject) => {
    geo.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy_m: Math.max(p.coords.accuracy, 0.1) }),
      (e) => reject(new GeoError(geoFailure(e.code))),
      GEO_OPTIONS,
    );
  });
}

export function uncertain(err: UiError): boolean {
  return err.status === 0 || err.status >= 500;
}

const FAILURES: Record<string, string> = {
  LOCATION_TOO_FAR: "explore.stamp.errors.tooFar",
  LOCATION_INACCURATE: "explore.stamp.errors.inaccurate",
  PLACE_REMOVED: "explore.stamp.errors.removed",
  PLACE_NOT_STAMPABLE: "explore.stamp.errors.notStampable",
  PLACE_NO_COORDINATES: "explore.stamp.errors.noCoordinates",
  PLACE_NOT_FOUND: "explore.stamp.errors.notFound",
  NETWORK: "explore.stamp.errors.network",
};

export function failureKey(code: string): string | null {
  return FAILURES[code] ?? null;
}

export function geoKey(reason: GeoFailure): string {
  return `explore.stamp.errors.geo.${reason}`;
}

export const manualAllowed = (code: string) => !["PLACE_REMOVED", "PLACE_NOT_STAMPABLE", "PLACE_NO_COORDINATES", "PLACE_NOT_FOUND"].includes(code);

const dayFormat = new Intl.DateTimeFormat("en-CA", { timeZone: TZ });

export function taipeiDay(iso: string): string {
  return dayFormat.format(new Date(iso));
}

export type DateLine = { key: "recorded" | "firstRecorded" | "verified"; at: string };

export function dateLines(ci: Pick<CheckIn, "verification_method" | "visited_at" | "verified_at">): DateLine[] {
  if (ci.verification_method === "manual" || !ci.verified_at) return [{ key: "recorded", at: ci.visited_at }];
  if (Date.parse(ci.verified_at) === Date.parse(ci.visited_at)) return [{ key: "verified", at: ci.verified_at }];
  return [
    { key: "firstRecorded", at: ci.visited_at },
    { key: "verified", at: ci.verified_at },
  ];
}

export function stampDay(ci: Pick<CheckIn, "verification_method" | "visited_at" | "verified_at">): string {
  return taipeiDay(ci.verified_at ?? ci.visited_at);
}
