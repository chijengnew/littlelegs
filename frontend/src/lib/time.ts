export const TZ = "Asia/Taipei";
export const MAX_DAY_OFFSET = 29;

export function taipeiToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(now);
}

export function addDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function dateRange(now: Date = new Date()): { min: string; max: string } {
  const min = taipeiToday(now);
  return { min, max: addDays(min, MAX_DAY_OFFSET) };
}

export function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

export function fromMinutes(total: number): string {
  const h = Math.floor(total / 60);
  const m = total % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export const QUARTER_TIMES: string[] = Array.from({ length: 96 }, (_, i) => fromMinutes(i * 15));

export function taipeiInstant(date: string, hhmm: string): Date {
  return new Date(`${date}T${hhmm}:00+08:00`);
}

export function formatClock(iso: string | null | undefined): string {
  if (!iso) return "--:--";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: TZ,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

export function formatDateLabel(isoDate: string): string {
  const d = new Date(`${isoDate}T12:00:00+08:00`);
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: TZ,
    month: "numeric",
    day: "numeric",
    weekday: "short",
  }).format(d);
}
