import { useTranslations } from "next-intl";
import type { Schemas } from "@/lib/api/client";
import { endpointName } from "@/lib/saved";
import { TZ, taipeiToday } from "@/lib/time";

export type Kind = "history" | "favorite";
export type HistoryItem = Schemas["HistoryItem"];
export type FavoriteItem = Schemas["FavoriteItem"];
export type SavedItem = HistoryItem | FavoriteItem;

export const isFavorite = (it: SavedItem): it is FavoriteItem => "saved_as" in it;
export const listHref = (kind: Kind) => (kind === "history" ? "/account?tab=history" : "/account?tab=favorites");
export const detailHref = (kind: Kind, id: string) => `/account/${kind === "history" ? "histories" : "favorites"}/${id}`;

const stampFormat = new Intl.DateTimeFormat("zh-TW", {
  timeZone: TZ,
  year: "numeric",
  month: "numeric",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const dayParts = new Intl.DateTimeFormat("zh-TW", { timeZone: TZ, month: "numeric", day: "numeric", weekday: "short" });

const narrowWeekday = new Intl.DateTimeFormat("zh-TW", { timeZone: TZ, weekday: "narrow" });

export function fullDate(isoDate: string): string {
  const weekday = narrowWeekday.format(new Date(`${isoDate}T12:00:00+08:00`));
  const [y, m, d] = isoDate.split("-");
  return `${y}/${Number(m)}/${Number(d)}（${weekday}）`;
}

export const isPast = (isoDate: string, today: string = taipeiToday()) => isoDate < today;

export function stopsOf(it: SavedItem): { name?: string | null; primary_type?: string | null }[] {
  return it.stops ?? it.stop_previews ?? [];
}

export function stopTypes(it: SavedItem, max = 3): string[] {
  const out: string[] = [];
  for (const x of stopsOf(it)) {
    if (x.primary_type && !out.includes(x.primary_type)) out.push(x.primary_type);
    if (out.length === max) break;
  }
  return out;
}

export type Status = { key: string; tone: "green" | "amber" | "red" };

export function statusOf(it: SavedItem): Status | null {
  if (isFavorite(it)) return it.saved_as === "plan" ? null : { key: `saved.savedAs.${it.saved_as}`, tone: "amber" };
  if (it.status === "failed") return { key: "saved.status.failed", tone: "red" };
  return it.plan_ordered ? { key: "saved.ordered", tone: "green" } : null;
}

export function dateTile(isoDate: string): { month: string; day: string; weekday: string } {
  const parts = dayParts.formatToParts(new Date(`${isoDate}T12:00:00+08:00`));
  const pick = (type: string) => parts.find((x) => x.type === type)?.value ?? "";
  return { month: pick("month"), day: pick("day"), weekday: pick("weekday") };
}

export function useSavedText() {
  const t = useTranslations();
  const fallback = { place: t("saved.unknownPlace"), custom: t("endpoint.customPlace"), device: t("endpoint.tabDevice") };
  const names = (it: SavedItem) => ({
    start: endpointName(it.conditions.start, it.start_place_name, it.start_label, fallback),
    end: it.conditions.end ? endpointName(it.conditions.end, it.end_place_name, it.end_label, fallback) : null,
  });
  return {
    names,
    title(it: SavedItem): { names: string; more: string | null } | null {
      const list = stopsOf(it).map((x) => x.name ?? t("saved.unknownPlace"));
      if (list.length === 0) return null;
      return { names: list.slice(0, 2).join("、"), more: list.length > 2 ? t("saved.more", { n: list.length }) : null };
    },
    subtitle(it: SavedItem, withDate = false): string[] {
      const n = names(it);
      const c = it.conditions;
      return [
        withDate ? fullDate(c.date) : "",
        `${c.depart_time}–${c.return_time}`,
        n.end ? t("saved.route", { start: n.start, end: n.end }) : t("saved.roundTripShort", { start: n.start }),
        t("saved.agesShort", { ages: c.children_ages.join("、") }),
      ].filter(Boolean);
    },
    stamp: (iso: string) => stampFormat.format(new Date(iso)),
  };
}
