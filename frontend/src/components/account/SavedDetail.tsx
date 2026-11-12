"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { api, type PlanResponse, type Schemas } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import { uuidv7 } from "@/lib/ids";
import { planScene, savedScene } from "@/lib/mapData";
import { endpointTarget, navigationUrl, placeTarget } from "@/lib/mapsUrl";
import { favoriteListId, queryListId, removeFavoritePacking, removeHistoryPacking } from "@/lib/packingStorage";
import { conditionsToForm, recheckBlock } from "@/lib/saved";
import { formatClock } from "@/lib/time";
import MapPanel, { useEndpointTitles } from "../MemberMap";
import NavLink from "../NavLink";
import PackingList from "../PackingList";
import { useAuth } from "../AuthProvider";
import { PlanStatus, Timeline } from "../PlanView";
import { usePlanner } from "../PlannerProvider";
import { SkeletonCard } from "../Skeleton";
import StatePanel from "../StatePanel";
import { ArrowLeftIcon, ArrowRightIcon } from "../icons";
import MemberGate from "./MemberGate";
import Segments from "./Segments";
import StopsTitle from "./StopsTitle";
import { detailHref, fullDate, isFavorite, isPast, listHref, statusOf, useSavedText, type Kind, type SavedItem } from "./savedText";
import ui from "../ui.module.css";
import a from "../auth/auth.module.css";
import s from "./account.module.css";

type T = ReturnType<typeof useTranslations>;
type Loaded = { item: SavedItem } | { notFound: true } | { error: string };

async function fetchItem(kind: Kind, id: string, t: T): Promise<Loaded> {
  try {
    const r = kind === "history"
      ? await api.GET("/v1/histories/{history_id}", { params: { path: { history_id: id } } })
      : await api.GET("/v1/favorites/{favorite_id}", { params: { path: { favorite_id: id } } });
    if (r.data) return { item: r.data };
    if (r.response.status === 404) return { notFound: true };
    return { error: toUiError(t, r.error, r.response.status).message };
  } catch (e) {
    return { error: toUiError(t, e).message };
  }
}

export default function SavedDetail({ kind }: { kind: Kind }) {
  const t = useTranslations();
  const { id } = useParams<{ id: string }>();
  return (
    <div className={a.wide}>
      <p className={s.back}>
        <Link className={ui.navLink} href={listHref(kind)}>
          <ArrowLeftIcon className={ui.arrowStart} />
          {t(kind === "history" ? "saved.backToHistory" : "saved.backToFavorites")}
        </Link>
      </p>
      <h1 className={a.title}>{t(kind === "history" ? "saved.historyTitle" : "saved.favoriteTitle")}</h1>
      <MemberGate next={detailHref(kind, id)}>
        <DetailBody key={id} kind={kind} id={id} />
      </MemberGate>
    </div>
  );
}

function DetailBody({ kind, id }: { kind: Kind; id: string }) {
  const t = useTranslations();
  const [loaded, setLoaded] = useState<Loaded | null>(null);

  useEffect(() => {
    let alive = true;
    fetchItem(kind, id, t).then((r) => { if (alive) setLoaded(r); });
    return () => { alive = false; };
  }, [kind, id, t]);

  if (!loaded) return <SkeletonCard lines={6} height={320} />;
  if ("notFound" in loaded) {
    return (
      <StatePanel
        tone="notFound"
        inline
        live="status"
        title={t("saved.notFound")}
        actions={<Link className={ui.primary} href={listHref(kind)}>{t(kind === "history" ? "saved.toHistory" : "saved.toFavorites")}</Link>}
      />
    );
  }
  if ("error" in loaded) {
    return (
      <StatePanel
        tone="error"
        inline
        live="alert"
        title={t("saved.loadFailed")}
        description={<p>{loaded.error}</p>}
        actions={
          <button type="button" className={ui.primary} onClick={() => { setLoaded(null); fetchItem(kind, id, t).then(setLoaded); }}>
            {t("saved.retry")}
          </button>
        }
      />
    );
  }
  return <Detail kind={kind} item={loaded.item} />;
}

function Detail({ kind, item }: { kind: Kind; item: SavedItem }) {
  const t = useTranslations();
  const text = useSavedText();
  const c = item.conditions;
  const names = text.names(item);
  const stops = item.stops ?? [];
  const blocked = recheckBlock(c);
  const titles = useEndpointTitles();
  const [rechecked, setRechecked] = useState<PlanResponse | null>(null);
  const map = useMemo(() => {
    if (rechecked) {
      return { hints: rechecked.map, scene: planScene(rechecked, rechecked.stops.map((x) => x.place_id), titles), missing: false };
    }
    const sc = savedScene(item, titles, t("saved.unknownPlace"));
    const hints: Schemas["MapHints"] = { mode: "google_map", connect_line: Boolean(sc.path), line_note: t("map.lineNote") };
    return { hints, scene: sc, missing: sc.missingEndpoint };
  }, [rechecked, item, titles, t]);
  const win = (w: Schemas["TimeWindow"]) => t("saved.window", { start: w.start, end: w.end });
  const slots = [
    { key: "nap", label: t("saved.nap"), w: c.nap },
    { key: "lunch", label: t("saved.lunch"), w: c.lunch },
    { key: "dinner", label: t("saved.dinner"), w: c.dinner },
  ];
  const unset = slots.filter((x) => !x.w).map((x) => x.key);
  const unsetLabels = [
    ...(unset.includes("nap") ? [t("saved.nap")] : []),
    ...(unset.includes("lunch") && unset.includes("dinner")
      ? [t("saved.meals")]
      : slots.filter((x) => x.key !== "nap" && !x.w).map((x) => x.label)),
  ];
  const title = text.title(item);
  const status = statusOf(item);
  const tone = { green: ui.chipGreen, amber: ui.chipAmber, red: ui.chipRed };

  return (
    <>
      <section className={ui.card}>
        <h2 className={title ? ui.cardTitle : `${ui.cardTitle} ${s.titleEmpty}`} style={{ marginBottom: 4 }}>{title ? <StopsTitle title={title} /> : t("saved.noStops")}</h2>
        <p className={s.subtitle}>
          <Segments items={text.subtitle(item, true)} />
        </p>
        <div className={s.meta}>
          {status && <span className={tone[status.tone]}>{t(status.key)}</span>}
          {isPast(c.date) && <span className={ui.chip}>{t("saved.expired")}</span>}
          <span>{t("saved.createdAt", { date: text.stamp(item.created_at) })}</span>
        </div>
        <p className={ui.hint} style={{ marginBottom: 0 }}>{t("saved.notice")}</p>
      </section>

      <section className={`${ui.card} ${s.section}`} aria-labelledby="saved-conditions">
        <h2 className={ui.cardTitle} id="saved-conditions">{t("saved.conditions")}</h2>
        <dl className={s.conditions}>
          <div><dt>{t("saved.date")}</dt><dd>{fullDate(c.date)}</dd></div>
          <div><dt>{t("saved.time")}</dt><dd>{c.depart_time}–{c.return_time}</dd></div>
          <div><dt>{t("saved.start")}</dt><dd>{names.start}</dd></div>
          <div><dt>{t("saved.end")}</dt><dd>{names.end ?? t("saved.endSame")}</dd></div>
          <div><dt>{t("saved.childrenLabel")}</dt><dd>{t("saved.ages", { ages: c.children_ages.join("、") })}</dd></div>
          {slots.filter((x) => x.w).map((x) => (
            <div key={x.key}><dt>{x.label}</dt><dd>{win(x.w!)}</dd></div>
          ))}
          {unsetLabels.length > 0 && <div><dt>{unsetLabels.join("、")}</dt><dd>{t("saved.none")}</dd></div>}
          <div><dt>{t("saved.rain")}</dt><dd>{t(c.rain_indoor_only ? "saved.yes" : "saved.no")}</dd></div>
          <div>
            <dt>{t("saved.facilities")}</dt>
            <dd>{c.facility_prefs?.length ? c.facility_prefs.map((k) => t(`facilities.${k}`)).join("、") : t("saved.none")}</dd>
          </div>
          <div>
            <dt>{t("saved.types")}</dt>
            <dd>{c.type_prefs?.length ? c.type_prefs.map((k) => t(`types.${k}`)).join("、") : t("saved.none")}</dd>
          </div>
        </dl>
      </section>

      {stops.length > 0 && (
        <section className={`${ui.card} ${s.section}`} aria-labelledby="saved-stops">
          <h2 className={ui.cardTitle} id="saved-stops">{t("saved.stops")}</h2>
          <ol className={s.stops}>
            {stops.map((x, i) => (
              <li key={x.place_id} className={s.stop}>
                <span className={s.badge} aria-hidden="true">{i + 1}</span>
                <div>
                  <strong>{x.name ?? t("saved.unknownPlace")}</strong>
                  <div className={s.meta}>
                    <span>{t("saved.stay", { m: x.stay_minutes })}</span>
                    {x.removed && <span className={ui.chipRed}>{t("saved.removed")}</span>}
                  </div>
                  {x.reasons_at_save.length > 0 && (
                    <p className={ui.hint} style={{ margin: "4px 0 0" }}>
                      {t("saved.reasonsAtSave", {
                        reasons: x.reasons_at_save
                          .map((r) => (t.has(`candidates.reasonTags.${r.code}`) ? t(`candidates.reasonTags.${r.code}`) : r.message))
                          .join("、"),
                      })}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>
          <div className={s.map}>
            <MapPanel hints={map.hints} scene={map.scene} legend="plan" />
            {map.missing && <p className={ui.hint} style={{ margin: 0 }}>{t("map.savedEndpointMissing")}</p>}
          </div>
        </section>
      )}

      {stops.length > 0 && <SavedNavigation item={item} names={names} />}
      {stops.length > 0 && (
        <PackingList
          listId={isFavorite(item) ? favoriteListId(item.id) : queryListId(item.query_id)}
          ages={c.children_ages}
          hasNap={Boolean(c.nap)}
          primaryTypes={stops.map((x) => x.primary_type)}
          className={s.section}
        />
      )}
      {stops.length > 0 && <Recheck kind={kind} item={item} names={names} blocked={blocked} onPlan={setRechecked} />}
      <Actions kind={kind} item={item} names={names} />
      <p className={`${ui.hint} ${s.feedback}`}>
        {t("feedback.planPrompt")}
        <Link className={ui.inlineNav} href="/feedback?from=saved_detail">
          {t("feedback.planLink")}
          <ArrowRightIcon className={ui.arrowEnd} />
        </Link>
      </p>
    </>
  );
}

function Recheck({ kind, item, names, blocked, onPlan }: {
  kind: Kind;
  item: SavedItem;
  names: { start: string; end: string | null };
  blocked: ReturnType<typeof recheckBlock>;
  onPlan: (plan: PlanResponse | null) => void;
}) {
  const t = useTranslations();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Schemas["RecheckResponse"] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const r = kind === "history"
        ? await api.POST("/v1/histories/{history_id}/recheck", { params: { path: { history_id: item.id } } })
        : await api.POST("/v1/favorites/{favorite_id}/recheck", { params: { path: { favorite_id: item.id } } });
      if (r.data) {
        setResult(r.data);
        onPlan(r.data.rechecked ? (r.data.plan ?? null) : null);
      } else setError(toUiError(t, r.error, r.response.status).message);
    } catch (e) {
      setError(toUiError(t, e).message);
    } finally {
      setBusy(false);
    }
  }

  if (blocked) return <p className={`${ui.bannerInfo} ${s.section}`} role="status">{t(`saved.blocked.${blocked}`)}</p>;
  const plan = result?.rechecked ? result.plan : null;
  const stops = (item.stops ?? []).map((x) => ({ place_id: x.place_id, name: x.name ?? t("saved.unknownPlace"), stay_minutes: x.stay_minutes }));
  const nameOf = (ref: string | null | undefined) => {
    if (!ref || ref === "?") return "?";
    if (ref === "start") return names.start;
    if (ref === "end") return names.end ?? names.start;
    return plan?.stops.find((x) => x.place_id === ref)?.name ?? stops.find((x) => x.place_id === ref)?.name ?? ref;
  };

  return (
    <section className={`${ui.card} ${s.section}`} aria-labelledby="saved-recheck">
      <div className={s.recheckHead}>
        <h2 className={ui.cardTitle} id="saved-recheck" style={{ margin: 0 }}>
          {t("saved.thisCheck")}{result?.checked_at ? `（${formatClock(result.checked_at)}）` : ""}
        </h2>
        {!plan && (
          <button type="button" className={ui.soft} onClick={run} disabled={busy} aria-busy={busy}>
            {busy ? t("saved.rechecking") : t("saved.recheck")}
          </button>
        )}
      </div>
      {result && !result.rechecked && <p className={ui.bannerInfo} role="status">{result.message}</p>}
      {error && <p className={ui.error} role="alert">{error}</p>}
      {plan && (
        <div style={{ display: "grid", gap: 12 }} aria-live="polite">
          <PlanStatus
            plan={plan}
            nameOf={nameOf}
            stops={stops}
            onStopsChange={() => {}}
            trip={{ date: item.conditions.date, depart: item.conditions.depart_time, arrive: item.conditions.return_time }}
            readOnly
          />
          <Timeline items={plan.timeline} nameOf={nameOf} stops={plan.stops} returnBy={item.conditions.return_time} />
          <button type="button" className={ui.soft} onClick={run} disabled={busy} aria-busy={busy} style={{ justifySelf: "start" }}>
            {busy ? t("saved.rechecking") : t("saved.recheck")}
          </button>
        </div>
      )}
    </section>
  );
}

function SavedNavigation({ item, names }: { item: SavedItem; names: { start: string; end: string | null } }) {
  const t = useTranslations();
  const endName = names.end ?? names.start;
  const stops = (item.stops ?? []).flatMap((x, i) => {
    const target = placeTarget(x);
    return target ? [{ key: x.place_id, name: `${i + 1}. ${x.name ?? ""}`, label: x.name ?? "", target }] : [];
  });
  const end = endpointTarget(item.end_endpoint, endName);
  const links = [
    ...stops,
    ...(end ? [{ key: "end", name: t("saved.navReturn", { name: endName }), label: endName, target: end }] : []),
  ];
  if (links.length === 0) return null;
  return (
    <section className={`${ui.card} ${s.section}`} aria-labelledby="saved-nav">
      <h2 className={ui.cardTitle} id="saved-nav">{t("saved.navTitle")}</h2>
      <p className={ui.bannerInfo} role="note">{t("saved.navNotChecked")}</p>
      <ul className={s.navList}>
        {links.map((x) => (
          <li key={x.key} className={s.navItem}>
            <span>{x.name}</span>
            <NavLink className={ui.soft} href={navigationUrl(x.target)} label={t("plan.navLegLabel", { name: x.label })}>
              {t("plan.navLeg")}
            </NavLink>
          </li>
        ))}
      </ul>
      <p className={ui.hint} style={{ margin: 0 }}>{t("plan.navNote")}</p>
    </section>
  );
}

function Actions({ kind, item, names }: { kind: Kind; item: SavedItem; names: { start: string; end: string | null } }) {
  const t = useTranslations();
  const router = useRouter();
  const auth = useAuth();
  const { startFrom } = usePlanner();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = useRef<string | null>(null);

  function replan() {
    startFrom(conditionsToForm(item.conditions, names));
    router.push("/planner");
  }

  async function remove() {
    key.current ??= uuidv7();
    setBusy(true);
    setError(null);
    try {
      const header = { "Idempotency-Key": key.current };
      const r = kind === "history"
        ? await api.DELETE("/v1/histories/{history_id}", { params: { path: { history_id: item.id }, header } })
        : await api.DELETE("/v1/favorites/{favorite_id}", { params: { path: { favorite_id: item.id }, header } });
      if (r.data) {
        if (auth.user) {
          if (isFavorite(item)) removeFavoritePacking(auth.user.uid, item.id);
          else removeHistoryPacking(auth.user.uid, item.query_id);
        }
        router.replace(`${listHref(kind)}&deleted=${r.data.status}`);
        return;
      }
      setError(r.response.status === 404 ? t("saved.notFound") : toUiError(t, r.error, r.response.status).message);
    } catch (e) {
      setError(toUiError(t, e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={`${ui.card} ${s.section}`}>
      <div className={s.actionRow}>
        <button type="button" className={ui.primary} onClick={replan}>{t("saved.replan")}</button>
        {!confirming && (
          <button type="button" className={`${ui.navLink} ${s.deleteLink}`} onClick={() => setConfirming(true)}>{t("saved.delete")}</button>
        )}
      </div>
      {confirming && (
        <div className={ui.bannerWarn} role="alertdialog" aria-labelledby="saved-delete">
          <div>
            <p id="saved-delete" style={{ margin: 0 }}>
              {t(kind === "history" ? "saved.deleteHistoryConfirm" : "saved.deleteFavoriteConfirm")}
            </p>
            <div className={s.actions}>
              <button type="button" className={ui.secondary} onClick={() => setConfirming(false)} disabled={busy}>{t("saved.cancel")}</button>
              <button type="button" className={ui.danger} onClick={remove} disabled={busy} aria-busy={busy}>
                {busy ? t("saved.deleting") : t("saved.confirmDelete")}
              </button>
            </div>
          </div>
        </div>
      )}
      {error && <p className={ui.error} role="alert">{error}</p>}
    </section>
  );
}
