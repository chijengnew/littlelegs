import { z } from "zod";
import type { Conditions, Endpoint } from "./api/client";
import { addDays, dateRange, taipeiInstant, toMinutes } from "./time";

export const FACILITY_PREFS = ["stroller_friendly", "nursing_room", "family_toilet"] as const;
export const TYPE_PREFS = [
  "parent_child_center",
  "zoo",
  "aquarium",
  "museum",
  "tourism_factory",
  "amusement_park",
  "industry_heritage",
  "diy_workshop",
  "env_edu",
  "nature_center",
  "farm",
  "park_playground",
  "library",
  "arts_venue",
  "night_market",
  "old_street",
  "street",
  "temple",
  "heritage",
  "indigenous",
  "hakka",
  "beach",
  "hot_spring",
  "bike_path",
  "trail",
  "shopping",
  "shop_cafe",
  "waterfront",
  "sports",
  "campus",
  "scenic_ride",
  "public_art",
  "community",
  "visitor_center",
  "station",
  "landmark",
  "nature",
  "other",
] as const;

export type EndpointChoice = { endpoint: NonNullable<Endpoint>; display: string };

export type WindowState = { enabled: boolean; start: string; end: string };

export type FormState = {
  date: string;
  depart_time: string;
  return_time: string;
  start: EndpointChoice | null;
  endSame: boolean;
  end: EndpointChoice | null;
  children: (number | null)[];
  nap: WindowState;
  lunch: WindowState;
  dinner: WindowState;
  rain_indoor_only: boolean;
  facility_prefs: (typeof FACILITY_PREFS)[number][];
  type_prefs: (typeof TYPE_PREFS)[number][];
};

export function initialForm(now: Date = new Date()): FormState {
  const { min } = dateRange(now);
  return {
    date: addDays(min, 1),
    depart_time: "09:00",
    return_time: "17:00",
    start: null,
    endSame: false,
    end: null,
    children: [null],
    nap: { enabled: false, start: "13:00", end: "14:30" },
    lunch: { enabled: false, start: "11:30", end: "13:00" },
    dinner: { enabled: false, start: "17:30", end: "19:00" },
    rain_indoor_only: false,
    facility_prefs: [],
    type_prefs: [],
  };
}

const quarter = z.string().regex(/^\d{2}:\d{2}$/).refine((v) => toMinutes(v) % 15 === 0, "quarter");

export type FieldKey =
  | "date"
  | "depart_time"
  | "return_time"
  | "start"
  | "end"
  | "children"
  | "nap"
  | "lunch"
  | "dinner";

export type FormErrors = Partial<Record<FieldKey, string>>;

export function validateForm(f: FormState, now: Date = new Date()): FormErrors {
  const errors: FormErrors = {};
  const { min, max } = dateRange(now);
  if (!f.date || f.date < min || f.date > max) errors.date = "validation.date";
  if (!quarter.safeParse(f.depart_time).success) errors.depart_time = "validation.quarter";
  if (!quarter.safeParse(f.return_time).success) errors.return_time = "validation.quarter";
  if (!errors.depart_time && !errors.return_time) {
    if (toMinutes(f.return_time) - toMinutes(f.depart_time) < 120) errors.return_time = "validation.returnGap";
  }
  if (!errors.date && !errors.depart_time && taipeiInstant(f.date, f.depart_time) <= now) {
    errors.depart_time = "validation.departPast";
  }
  const ages = z.array(z.number().int().min(0).max(18)).min(1).max(5);
  if (f.children.some((a) => a === null) || !ages.safeParse(f.children).success) {
    errors.children = "validation.children";
  }
  if (!f.start) errors.start = "validation.start";
  if (!f.endSame && !f.end) errors.end = "validation.end";

  const dep = toMinutes(f.depart_time);
  const ret = toMinutes(f.return_time);
  const inTrip = (w: WindowState) => toMinutes(w.start) >= dep && toMinutes(w.end) <= ret;
  if (f.nap.enabled && (toMinutes(f.nap.start) >= toMinutes(f.nap.end) || !inTrip(f.nap))) {
    errors.nap = "validation.window";
  }
  for (const k of ["lunch", "dinner"] as const) {
    const w = f[k];
    if (w.enabled && (toMinutes(w.end) - toMinutes(w.start) < 60 || !inTrip(w))) errors[k] = "validation.meal";
  }
  return errors;
}

export function toConditions(f: FormState): Conditions {
  const win = (w: WindowState) => (w.enabled ? { start: w.start, end: w.end } : null);
  return {
    schema_version: 1,
    date: f.date,
    depart_time: f.depart_time,
    return_time: f.return_time,
    start: f.start!.endpoint,
    end: f.endSame ? null : f.end!.endpoint,
    travel_mode: "drive",
    children_ages: f.children as number[],
    nap: win(f.nap),
    lunch: win(f.lunch),
    dinner: win(f.dinner),
    rain_indoor_only: f.rain_indoor_only,
    facility_prefs: [...f.facility_prefs].sort(),
    type_prefs: [...f.type_prefs].sort(),
  };
}

export function fieldFromLoc(loc: string): FieldKey | null {
  const m = loc.match(/^conditions\.?([a-z_]+)?/);
  if (!m) return null;
  const k = m[1];
  if (k === "children_ages") return "children";
  if (k && ["date", "depart_time", "return_time", "start", "end", "nap", "lunch", "dinner"].includes(k)) {
    return k as FieldKey;
  }
  return "return_time";
}
