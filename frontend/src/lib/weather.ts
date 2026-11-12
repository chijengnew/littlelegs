import type { Schemas } from "./api/client";
import { fromMinutes, toMinutes } from "./time";

export type TripPart = { label: string; from: string; to: string; percent: number | null };

function minutesOf(iso: string | null, tripDate: string): number | null {
  const m = iso ? /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/.exec(iso) : null;
  if (!m) return null;
  const day = m[1] === tripDate ? 0 : m[1] > tripDate ? 1440 : -1440;
  return day + Number(m[2]) * 60 + Number(m[3]);
}

export function tripParts(
  weather: { parts: Schemas["WeatherPartOut"][] },
  tripDate: string,
  depart: string,
  arrive: string,
): TripPart[] {
  const w0 = toMinutes(depart);
  const w1 = toMinutes(arrive);
  const out: { label: string; from: number; to: number; percent: number | null }[] = [];
  for (const p of weather.parts) {
    const a = minutesOf(p.start, tripDate);
    const b = minutesOf(p.end, tripDate);
    if (a === null || b === null) continue;
    const from = Math.max(a, w0);
    const to = Math.min(b, w1);
    if (to > from) out.push({ label: p.label, from, to, percent: p.percent });
  }
  return out
    .sort((x, y) => x.from - y.from)
    .map((p) => ({ label: p.label, from: fromMinutes(p.from), to: fromMinutes(p.to), percent: p.percent }));
}

export function tripMax(
  area: { parts: Schemas["WeatherPartOut"][] },
  tripDate: string,
  depart: string,
  arrive: string,
): number | null {
  const values = tripParts(area, tripDate, depart, arrive)
    .map((p) => p.percent)
    .filter((x): x is number => x !== null);
  return values.length ? Math.max(...values) : null;
}
