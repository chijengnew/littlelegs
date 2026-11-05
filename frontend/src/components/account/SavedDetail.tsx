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
import { formatClock, formatDateLabel } from "@/lib/time";
import MapPanel, { useEndpointTitles } from "../MemberMap";
import NavLink from "../NavLink";
import PackingList from "../PackingList";
import { useAuth } from "../AuthProvider";
import { FeasibilityCard, Timeline } from "../PlanView";
import { usePlanner } from "../PlannerProvider";
import { WeatherNotice } from "../SidePanels";
import { SkeletonCard } from "../Skeleton";
import MemberGate from "./MemberGate";
import { detailHref, isFavorite, listHref, useSavedText, type Kind, type SavedItem } from "./savedText";
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
      <p style={{ margin: "0 0 8px" }}>
        <Link href={listHref(kind)}>{t(kind === "history" ? "saved.backToHistory" : "saved.backToFavorites")}</Link>
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
  if ("notFound" in loaded) return <p className={ui.bannerWarn} role="status">{t("saved.notFound")}</p>;
  if ("error" in loaded) {
    return (
      <div className={ui.bannerError} role="alert">
        <span>{t("saved.loadFailed")} {loaded.error}</span>
        <button type="button" className={ui.soft} onClick={() => { setLoaded(null); fetchItem(kind, id, t).then(setLoaded); }}>
          {t("saved.retry")}
        </button>
      </div>
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
  const win = (w: Schemas["TimeWindow"] | null | undefined) => (w ? t("saved.window", { start: w.start, end: w.end }) : t("saved.none"));

  return (
    <>
      <section className={ui.card}>
        <h2 className={ui.cardTitle} style={{ marginBottom: 4 }}>{text.route(item)}</h2>
        <div className={s.meta}>
          <span>{text.trip(item)}</span>
          {isFavorite(item) ? (
            <span className={item.saved_as === "plan" ? ui.chipBlue : ui.chipAmber}>{t(`saved.savedAs.${item.saved_as}`)}</span>
          ) : (
            <>
              <span className={ui.chip}>{t.has(`saved.status.${item.status}`) ? t(`saved.status.${item.status}`) : item.status}</span>
              <span className={item.plan_ordered ? ui.chipGreen : ui.chip}>{t(item.plan_ordered ? "saved.ordered" : "saved.notOrdered")}</span>
            </>
          )}
          <span>{t("saved.createdAt", { date: text.stamp(item.created_at) })}</span>
        </div>
        {item.notice && <p className={ui.hint} style={{ marginBottom: 0 }}>{item.notice}</p>}
      </section>

      <section className={`${ui.card} ${s.section}`} aria-labelledby="saved-conditions">
        <h2 className={ui.cardTitle} id="saved-conditions">{t("saved.conditions")}</h2>
        <dl className={s.details}>
          <dt>{t("saved.date")}</dt><dd>{c.date}（{formatDateLabel(c.date)}）</dd>
          <dt>{t("saved.time")}</dt><dd>{c.depart_time}–{c.return_time}</dd>
          <dt>{t("saved.start")}</dt><dd>{names.start}</dd>
          <dt>{t("saved.end")}</dt><dd>{names.end ?? t("saved.endSame")}</dd>
          <dt>{t("saved.childrenLabel")}</dt><dd>{t("saved.ages", { ages: c.children_ages.join("、") })}</dd>
          <dt>{t("saved.nap")}</dt><dd>{win(c.nap)}</dd>
          <dt>{t("saved.lunch")}</dt><dd>{win(c.lunch)}</dd>
          <dt>{t("saved.dinner")}</dt><dd>{win(c.dinner)}</dd>
          <dt>{t("saved.rain")}</dt><dd>{t(c.rain_indoor_only ? "saved.yes" : "saved.no")}</dd>
          <dt>{t("saved.facilities")}</dt>
          <dd>{c.facility_prefs?.length ? c.facility_prefs.map((k) => t(`facilities.${k}`)).join("、") : t("saved.none")}</dd>
          <dt>{t("saved.types")}</dt>
          <dd>{c.type_prefs?.length ? c.type_prefs.map((k) => t(`types.${k}`)).join("、") : t("saved.none")}</dd>
        </dl>
      </section>

      <section className={`${ui.card} ${s.section}`} aria-labelledby="saved-stops">
        <h2 className={ui.cardTitle} id="saved-stops">{t("saved.stops")}</h2>
        {stops.length === 0 ? (
          <p className={ui.hint}>{t("saved.noStops")}</p>
        ) : (
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
                      {t("saved.reasonsAtSave", { reasons: x.reasons_at_save.map((r) => r.message).join("、") })}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
        {stops.length > 0 && (
          <div className={s.map}>
            <MapPanel hints={map.hints} scene={map.scene} legend="plan" />
            {map.missing && <p className={ui.hint} style={{ margin: 0 }}>{t("map.savedEndpointMissing")}</p>}
          </div>
        )}
      </section>

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
      {stops.length > 0 && <Recheck kind={kind} item={item} blocked={blocked} onPlan={setRechecked} />}
      <Actions kind={kind} item={item} names={names} />
      <p className={ui.hint}>
        {t("feedback.planPrompt")} <Link href="/feedback?from=saved_detail">{t("feedback.planLink")}</Link>
      </p>
    </>
  );
}

function Recheck({ kind, item, blocked, onPlan }: {
  kind: Kind;
  item: SavedItem;
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
    if (ref === "start") return t("plan.start");
    if (ref === "end") return t("plan.end");
    return plan?.stops.find((x) => x.place_id === ref)?.name ?? stops.find((x) => x.place_id === ref)?.name ?? ref;
  };

  return (
    <section className={`${ui.card} ${s.section}`} aria-labelledby="saved-recheck">
      <h2 className={ui.cardTitle} id="saved-recheck">
        {t("saved.thisCheck")}{result?.checked_at ? `（${formatClock(result.checked_at)}）` : ""}
      </h2>
      {!plan && (
        <>
          <p className={ui.hint}>{t("saved.recheckHint")}</p>
          <button type="button" className={ui.soft} onClick={run} disabled={busy} aria-busy={busy}>
            {busy ? t("saved.rechecking") : t("saved.recheck")}
          </button>
        </>
      )}
      {result && !result.rechecked && <p className={ui.bannerInfo} role="status">{result.message}</p>}
      {error && <p className={ui.error} role="alert">{error}</p>}
      {plan && (
        <div style={{ display: "grid", gap: 12 }} aria-live="polite">
          {plan.weather && <WeatherNotice weather={plan.weather} />}
          <FeasibilityCard plan={plan} nameOf={nameOf} stops={stops} onStopsChange={() => {}} readOnly />
          <Timeline items={plan.timeline} nameOf={nameOf} />
          {plan.notices.length > 0 && (
            <ul className={ui.hint} style={{ margin: 0, paddingLeft: 18 }}>
              {plan.notices.map((n) => <li key={n}>{n}</li>)}
            </ul>
          )}
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
    router.push("/");
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
      <div className={s.actions} style={{ marginTop: 0 }}>
        <button type="button" className={ui.primary} onClick={replan}>{t("saved.replan")}</button>
        {!confirming && <button type="button" className={ui.secondary} onClick={() => setConfirming(true)}>{t("saved.delete")}</button>}
      </div>
      <p className={ui.hint}>{t("saved.replanHint")}</p>
      {confirming && (
        <div className={ui.bannerWarn} role="alertdialog" aria-labelledby="saved-delete">
          <div>
            <p id="saved-delete" style={{ margin: 0 }}>
              {t(kind === "history" ? "saved.deleteHistoryConfirm" : "saved.deleteFavoriteConfirm")}
            </p>
            <div className={s.actions}>
              <button type="button" className={ui.danger} onClick={remove} disabled={busy} aria-busy={busy}>
                {busy ? t("saved.deleting") : t("saved.confirmDelete")}
              </button>
              <button type="button" className={ui.soft} onClick={() => setConfirming(false)} disabled={busy}>{t("saved.cancel")}</button>
            </div>
          </div>
        </div>
      )}
      {error && <p className={ui.error} role="alert">{error}</p>}
    </section>
  );
}
