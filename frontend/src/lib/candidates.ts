import type { Candidate, Schemas } from "./api/client";

type Coded = Schemas["Coded"];

const SHOWN_AS_CHIP = new Set(["stay_estimated", "indoor_inferred"]);

export function sharedWarnings(items: readonly Candidate[]): Coded[] {
  if (items.length < 2) return [];
  const [first, ...rest] = items;
  return first.warnings.filter(
    (w) => !SHOWN_AS_CHIP.has(w.code) && rest.every((c) => c.warnings.some((x) => x.code === w.code)),
  );
}

export function ownWarnings(item: Candidate, shared: readonly Coded[]): Coded[] {
  const skip = new Set(shared.map((w) => w.code));
  return item.warnings.filter((w) => !SHOWN_AS_CHIP.has(w.code) && !skip.has(w.code));
}

const AREA = /^(\S{2,3}?[市縣])(\S{1,4}?[區鄉鎮市])/;

export function areaOf(address: string | null | undefined, city?: string | null): string | null {
  const rest = (address ?? "").trim().replace(/^\d{3,6}\s*/, "").replace(/^(台灣|臺灣)/, "");
  const m = AREA.exec(rest);
  if (m) return m[1] + m[2];
  return city?.trim() || null;
}
