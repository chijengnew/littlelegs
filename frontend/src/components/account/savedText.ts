import { useTranslations } from "next-intl";
import type { Schemas } from "@/lib/api/client";
import { endpointName } from "@/lib/saved";
import { TZ, formatDateLabel } from "@/lib/time";

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

export function useSavedText() {
  const t = useTranslations();
  const fallback = { place: t("saved.unknownPlace"), custom: t("endpoint.customPlace"), device: t("endpoint.tabDevice") };
  const names = (it: SavedItem) => ({
    start: endpointName(it.conditions.start, it.start_place_name, it.start_label, fallback),
    end: it.conditions.end ? endpointName(it.conditions.end, it.end_place_name, it.end_label, fallback) : null,
  });
  return {
    names,
    route(it: SavedItem) {
      const n = names(it);
      return n.end ? t("saved.route", { start: n.start, end: n.end }) : t("saved.roundTrip", { start: n.start });
    },
    trip: (it: SavedItem) => `${formatDateLabel(it.conditions.date)} ${it.conditions.depart_time}–${it.conditions.return_time}`,
    children: (it: SavedItem) => t("saved.children", { ages: it.conditions.children_ages.join("、") }),
    stamp: (iso: string) => stampFormat.format(new Date(iso)),
  };
}
