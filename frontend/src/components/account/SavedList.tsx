"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import { SkeletonList } from "../Skeleton";
import { detailHref, isFavorite, useSavedText, type Kind, type SavedItem } from "./savedText";
import ui from "../ui.module.css";
import s from "./account.module.css";

const PAGE_SIZE = 15;
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
      <div className={`${ui.bannerError} ${s.section}`} role="alert">
        <span>{t("saved.loadFailed")} {error}</span>
        <button type="button" className={ui.soft} onClick={() => load(null)} disabled={busy}>{t("saved.retry")}</button>
      </div>
    );
  }
  if (items.length === 0) {
    return <p className={`${ui.card} ${s.section}`}>{t(kind === "history" ? "saved.historyEmpty" : "saved.favoritesEmpty")}</p>;
  }
  return (
    <>
      <ul className={s.list}>
        {items.map((it) => (
          <li key={it.id}>
            <Link href={detailHref(kind, it.id)} className={`${ui.card} ${s.item}`}>
              <div className={s.itemTitle}>{text.route(it)}</div>
              <div className={s.meta}>
                <span>{text.trip(it)}</span>
                <span>{text.children(it)}</span>
                {isFavorite(it) ? (
                  <span className={it.saved_as === "plan" ? ui.chipBlue : ui.chipAmber}>{t(`saved.savedAs.${it.saved_as}`)}</span>
                ) : (
                  <>
                    <span className={it.status === "failed" ? ui.chipRed : ui.chip}>
                      {t.has(`saved.status.${it.status}`) ? t(`saved.status.${it.status}`) : it.status}
                    </span>
                    {it.plan_ordered && <span className={ui.chipGreen}>{t("saved.ordered")}</span>}
                  </>
                )}
              </div>
              <div className={s.meta}>
                {isFavorite(it)
                  ? t("saved.createdAt", { date: text.stamp(it.created_at) })
                  : t("saved.updatedAt", { date: text.stamp(it.updated_at) })}
              </div>
            </Link>
          </li>
        ))}
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
