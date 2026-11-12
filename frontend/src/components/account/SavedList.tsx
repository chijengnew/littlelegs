"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import StatePanel from "../StatePanel";
import { SkeletonList } from "../Skeleton";
import PlaceArt from "../art/PlaceArt";
import Segments from "./Segments";
import StopsTitle from "./StopsTitle";
import { dateTile, detailHref, isFavorite, isPast, statusOf, stopTypes, useSavedText, type Kind, type SavedItem } from "./savedText";
import ui from "../ui.module.css";
import s from "./account.module.css";

const PAGE_SIZE = 15;
const TONE = { green: ui.chipGreen, amber: ui.chipAmber, red: ui.chipRed };
type Page = { items: SavedItem[]; next: string | null } | { error: string };
type T = ReturnType<typeof useTranslations>;

async function fetchPage(kind: Kind, cursor: string | null, t: T): Promise<Page> {
  const query = { limit: PAGE_SIZE, ...(cursor ? { cursor } : {}) };
  try {
    const r = kind === "history"
      ? await api.GET("/v1/histories", { params: { query } })
      : await api.GET("/v1/favorites", { params: { query } });
    if (r.data) return { items: r.data.items, next: r.data.next_cursor };
    return { error: toUiError(t, r.error, r.response.status).message };
  } catch (e) {
    return { error: toUiError(t, e).message };
  }
}

export default function SavedList({ kind }: { kind: Kind }) {
  const t = useTranslations();
  const text = useSavedText();
  const [items, setItems] = useState<SavedItem[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchPage(kind, null, t).then((p) => {
      if (!alive) return;
      if ("error" in p) setError(p.error);
      else {
        setItems(p.items);
        setNext(p.next);
      }
    });
    return () => { alive = false; };
  }, [kind, t]);

  async function load(cursor: string | null) {
    setBusy(true);
    setError(null);
    const p = await fetchPage(kind, cursor, t);
    setBusy(false);
    if ("error" in p) setError(p.error);
    else {
      setItems((prev) => (cursor && prev ? [...prev, ...p.items] : p.items));
      setNext(p.next);
    }
  }

  if (!items) {
    if (!error) return <div className={s.section} aria-busy="true"><SkeletonList count={3} lines={2} /></div>;
    return (
      <StatePanel
        tone="error"
        inline
        live="alert"
        title={t("saved.loadFailed")}
        description={<p>{error}</p>}
        actions={<button type="button" className={ui.primary} onClick={() => load(null)} disabled={busy}>{t("saved.retry")}</button>}
      />
    );
  }
  if (items.length === 0) {
    return (
      <StatePanel
        tone="empty"
        inline
        title={t(kind === "history" ? "saved.historyEmptyTitle" : "saved.favoritesEmptyTitle")}
        description={<p>{t(kind === "history" ? "saved.historyEmpty" : "saved.favoritesEmpty")}</p>}
        actions={<Link className={ui.primary} href="/planner">{t("app.startPlanning")}</Link>}
      />
    );
  }
  return (
    <>
      <ul className={s.list}>
        {items.map((it) => {
          const day = dateTile(it.conditions.date);
          const past = isPast(it.conditions.date);
          const title = text.title(it);
          const status = statusOf(it);
          const types = stopTypes(it);
          return (
            <li key={it.id}>
              <Link href={detailHref(kind, it.id)} className={s.item}>
                <span className={past ? `${s.dateTile} ${s.datePast}` : s.dateTile}>
                  <span className={s.dateMonth}>{t("saved.tileMonth", { m: day.month })}</span>
                  <span className={s.dateDay}>{day.day}</span>
                  <span className={s.dateWeek}>{past ? t("saved.expired") : day.weekday}</span>
                </span>
                <span className={s.itemBody}>
                  <span className={title ? s.itemTitle : `${s.itemTitle} ${s.itemTitleEmpty}`}>{title ? <StopsTitle title={title} /> : t("saved.noStops")}</span>
                  <span className={`${s.itemMeta} ${s.itemSub}`}>
                    <Segments items={text.subtitle(it)} />
                  </span>
                  <span className={s.itemMeta}>
                    {status && <span className={TONE[status.tone]}>{t(status.key)}</span>}
                    <span className={s.stamp}>
                      {isFavorite(it)
                        ? t("saved.createdAt", { date: text.stamp(it.created_at) })
                        : t("saved.updatedAt", { date: text.stamp(it.updated_at) })}
                    </span>
                  </span>
                </span>
                {types.length > 0 && (
                  <span className={s.typeIcons} aria-hidden="true">
                    {types.map((x) => <PlaceArt key={x} type={x} className={s.typeIcon} />)}
                  </span>
                )}
                <span className={s.chevron} aria-hidden="true">›</span>
              </Link>
            </li>
          );
        })}
      </ul>
      {error && <p className={ui.error} role="alert">{t("saved.loadFailed")} {error}</p>}
      {next && (
        <div className={s.more}>
          <button type="button" className={ui.secondary} onClick={() => load(next)} disabled={busy} aria-busy={busy}>
            {t("saved.loadMore")}
          </button>
        </div>
      )}
    </>
  );
}
