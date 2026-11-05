import type { Conditions, Endpoint } from "./api/client";
import { initialForm, type FormState, type WindowState } from "./form";
import { addDays, dateRange, taipeiInstant, taipeiToday } from "./time";

export const RECHECK_MAX_OFFSET = 6;

export type RecheckBlock = "DEPARTURE_PASSED" | "OUTSIDE_EXTERNAL_COVERAGE";

export function recheckBlock(c: Pick<Conditions, "date" | "depart_time">, now: Date = new Date()): RecheckBlock | null {
  if (taipeiInstant(c.date, c.depart_time) <= now) return "DEPARTURE_PASSED";
  if (c.date > addDays(taipeiToday(now), RECHECK_MAX_OFFSET)) return "OUTSIDE_EXTERNAL_COVERAGE";
  return null;
}

export type EndpointFallbacks = { place: string; custom: string; device: string };

export function endpointName(
  ep: NonNullable<Endpoint>,
  placeName: string | null | undefined,
  label: string | null | undefined,
  fallback: EndpointFallbacks,
): string {
  if (ep.type === "place_ref") return placeName || fallback.place;
  if (ep.type === "google_place") return label || fallback.custom;
  return label || fallback.device;
}

export function conditionsToForm(
  c: Conditions,
  display: { start: string; end: string | null },
  now: Date = new Date(),
): FormState {
  const base = initialForm(now);
  const { min, max } = dateRange(now);
  const win = (w: Conditions["nap"], fallback: WindowState): WindowState =>
    w ? { enabled: true, start: w.start, end: w.end } : { ...fallback, enabled: false };
  return {
    ...base,
    date: c.date >= min && c.date <= max ? c.date : base.date,
    depart_time: c.depart_time,
    return_time: c.return_time,
    start: { endpoint: c.start, display: display.start },
    endSame: !c.end,
    end: c.end ? { endpoint: c.end, display: display.end ?? display.start } : null,
    children: [...c.children_ages],
    nap: win(c.nap, base.nap),
    lunch: win(c.lunch, base.lunch),
    dinner: win(c.dinner, base.dinner),
    rain_indoor_only: c.rain_indoor_only,
    facility_prefs: [...(c.facility_prefs ?? [])],
    type_prefs: [...(c.type_prefs ?? [])],
  };
}
