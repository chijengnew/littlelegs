"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { api, type Schemas } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import { uuidv7 } from "@/lib/ids";
import { stampDay, type CheckIn } from "@/lib/stamping";
import StatePanel from "../StatePanel";
import { SkeletonList } from "../Skeleton";
import { CheckInDates, MethodChip } from "./CheckInDates";
import { Stamp } from "./ExploreArt";
import PlaceSearch from "./PlaceSearch";
import ui from "../ui.module.css";
import s from "./explore.module.css";

const PAGE_SIZE = 24;
type Counts = Schemas["CheckInCounts"];
type Page = { items: CheckIn[]; next: string | null; counts: Counts } | { error: string };
type T = ReturnType<typeof useTranslations>;

async function fetchPage(cursor: string | null, t: T): Promise<Page> {
  try {
    const r = await api.GET("/v1/check-ins", { params: { query: { limit: PAGE_SIZE, ...(cursor ? { cursor } : {}) } } });
    if (r.data) return { items: r.data.items, next: r.data.next_cursor, counts: r.data.counts };
    return { error: toUiError(t, r.error, r.response.status).message };
  } catch (e) {
    return { error: toUiError(t, e).message };
  }
}

export default function Passport() {
  const t = useTranslations();
  const [items, setItems] = useState<CheckIn[] | null>(null);
  const [counts, setCounts] = useState<Counts | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    let alive = true;
    fetchPage(null, t).then((p) => {
      if (!alive) return;
      if ("error" in p) setError(p.error);
      else {
        setItems(p.items);
        setNext(p.next);
        setCounts(p.counts);
        setError(null);
      }
    });
    return () => {
      alive = false;
    };
  }, [t]);

  async function load(cursor: string | null) {
    setBusy(true);
    setError(null);
    const p = await fetchPage(cursor, t);
    setBusy(false);
    if ("error" in p) setError(p.error);
    else {
      setItems((prev) => (cursor && prev ? [...prev, ...p.items] : p.items));
      setNext(p.next);
      setCounts(p.counts);
    }
  }

  function removed(item: CheckIn, completed: boolean) {
    setItems((prev) => prev?.filter((x) => x.id !== item.id) ?? prev);
    setCounts((c) => c && { total: c.total - 1, location: c.location - (item.verification_method === "location" ? 1 : 0), manual: c.manual - (item.verification_method === "manual" ? 1 : 0) });
    setNotice({ ok: true, text: t(completed ? "explore.passport.deleted" : "explore.passport.deleteAccepted") });
  }

  if (!items) {
    if (!error) return <div aria-busy="true"><SkeletonList count={3} lines={2} /></div>;
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

  return (
    <>
      {counts && counts.total > 0 && (
        <div className={s.summary}>
          <h2>{t("explore.passport.summary", { n: counts.total })}</h2>
          <span className={ui.chipGreen}>{t("explore.passport.countLocation", { n: counts.location })}</span>
          <span className={ui.chip}>{t("explore.passport.countManual", { n: counts.manual })}</span>
        </div>
      )}
      {notice && <p className={notice.ok ? ui.bannerOk : ui.bannerError} role="status">{notice.text}</p>}
      <PlaceSearch />
      {items.length === 0 ? (
        <StatePanel
          tone="empty"
          inline
          title={t("explore.passport.emptyTitle")}
          description={<p>{t("explore.passport.empty")}</p>}
          actions={<Link className={ui.primary} href="/planner">{t("app.startPlanning")}</Link>}
        />
      ) : (
        <ul className={s.wall}>
          {items.map((it) => (
            <li key={it.id}>
              <Entry item={it} onDeleted={removed} onError={(text) => setNotice({ ok: false, text })} />
            </li>
          ))}
        </ul>
      )}
      {error && <p className={ui.error} role="alert">{t("saved.loadFailed")} {error}</p>}
      {next && (
        <div className={s.more}>
          <button type="button" className={ui.secondary} onClick={() => load(next)} disabled={busy} aria-busy={busy}>
            {t("saved.loadMore")}
          </button>
        </div>
      )}
      {items.length > 0 && <p className={s.note}>{t("explore.passport.note")}</p>}
    </>
  );
}

function Entry({
  item,
  onDeleted,
  onError,
}: {
  item: CheckIn;
  onDeleted: (item: CheckIn, completed: boolean) => void;
  onError: (text: string) => void;
}) {
  const t = useTranslations();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const key = useRef<string | null>(null);

  async function remove() {
    if (deleting) return;
    key.current ??= uuidv7();
    setDeleting(true);
    try {
      const { data, error, response } = await api.DELETE("/v1/check-ins/{check_in_id}", {
        params: { path: { check_in_id: item.id }, header: { "Idempotency-Key": key.current } },
      });
      if (data) {
        onDeleted(item, data.status === "completed");
        return;
      }
      if (response.status === 404) {
        onDeleted(item, true);
        return;
      }
      onError(`${t("explore.passport.deleteFailed")} ${toUiError(t, error, response.status).message}`);
    } catch (e) {
      onError(`${t("explore.passport.deleteFailed")} ${toUiError(t, e).message}`);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <article className={s.entry} aria-labelledby={`ci-${item.id}`}>
      <Stamp type={item.place.primary_type} method={item.verification_method} label={stampDay(item).replaceAll("-", ".")} size={92} />
      <div className={s.entryBody}>
        <Link href={`/places/${item.place.place_id}?from=passport`} className={s.entryName} id={`ci-${item.id}`}>
          {item.place.name}
        </Link>
        <div className={s.chips}>
          <MethodChip method={item.verification_method} />
          {item.place.primary_type && <span className={ui.chipBlue}>{t(`types.${item.place.primary_type}`)}</span>}
          {item.place.removed && <span className={ui.chipAmber}>{t("explore.passport.removed")}</span>}
        </div>
        <CheckInDates checkIn={item} />
      </div>
      <div className={s.entryFoot}>
        {confirming ? (
          <>
            <p role="alert">{t("explore.passport.deleteConfirm")}</p>
            <button type="button" className={ui.secondary} onClick={() => setConfirming(false)} disabled={deleting}>
              {t("saved.cancel")}
            </button>
            <button type="button" className={ui.danger} onClick={remove} disabled={deleting} aria-busy={deleting}>
              {t("saved.confirmDelete")}
            </button>
          </>
        ) : (
          <button type="button" className={s.textDanger} onClick={() => setConfirming(true)} aria-label={t("explore.passport.deleteLabel", { name: item.place.name })}>
            {t("explore.passport.delete")}
          </button>
        )}
      </div>
    </article>
  );
}
