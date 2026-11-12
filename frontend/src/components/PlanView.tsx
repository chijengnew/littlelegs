"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { PlanResponse, Schemas } from "@/lib/api/client";
import FavoriteButton from "./FavoriteButton";
import { planScene } from "@/lib/mapData";
import { endpointTarget, planLegUrl, placeTarget, routeUrl } from "@/lib/mapsUrl";
import { queryListId } from "@/lib/packingStorage";
import { formatClock, taipeiToday, toMinutes } from "@/lib/time";
import { tripMax } from "@/lib/weather";
import PlaceArt from "./art/PlaceArt";
import { useAuth } from "./AuthProvider";
import MapPanel, { MapHint, mapStateOf, useEndpointTitles } from "./MemberMap";
import NavLink from "./NavLink";
import PackingList from "./PackingList";
import { usePlanner } from "./PlannerProvider";
import { WeatherCard } from "./SidePanels";
import { SkeletonCard, appear } from "./Skeleton";
import TripChips from "./TripChips";
import ViewSwitch from "./ViewSwitch";
import {
  AlertIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  CarIcon,
  ChunkyCloseIcon,
  ChunkyDownIcon,
  ChunkyUpIcon,
  ClockIcon,
  FlagIcon,
  MapIcon,
  MealIcon,
  MoonIcon,
  NavigateIcon,
  PencilIcon,
  TimelineIcon,
} from "./icons";
import ui from "./ui.module.css";
import s from "./PlanView.module.css";

export type EditStop = { place_id: string; name: string; stay_minutes: number | null; default_stay_minutes?: number };
export type Trip = { date: string; depart: string; arrive: string };
type Names = (ref: string | null | undefined) => string;
type PlanStop = Schemas["PlanStopOut"];

type Props = {
  plan: PlanResponse | null;
  stops: EditStop[];
  dirty: boolean;
  busy: boolean;
  loading?: boolean;
  onStopsChange: (stops: EditStop[]) => void;
  onRestore: (stops: EditStop[]) => void;
  onCheck: () => void;
  onBack: () => void;
};

const STAY_OPTIONS = Array.from({ length: 24 }, (_, i) => (i + 1) * 15);
const KEEP_WARNINGS = new Set(["special_hours_unverified", "travel_unavailable", "search_incomplete", "place_removed"]);

export default function PlanView({ plan, stops, dirty, busy, loading = false, onStopsChange, onRestore, onCheck, onBack }: Props) {
  const t = useTranslations();
  const { form } = usePlanner();
  const { member } = useAuth();
  const titles = useEndpointTitles();
  const [view, setView] = useState<"timeline" | "map">("timeline");
  const [editingFor, setEditingFor] = useState<PlanResponse | null | undefined>(undefined);
  const editing = dirty || (editingFor !== undefined && editingFor === plan);
  const clean = useRef<EditStop[] | null>(null);
  const scene = useMemo(() => (plan ? planScene(plan, stops.map((x) => x.place_id), titles) : null), [plan, stops, titles]);
  const mapState = mapStateOf(Boolean(member), plan?.map);
  const mapReady = mapState === "ready";
  const fresh = plan && !dirty;

  useEffect(() => {
    if (!dirty) clean.current = stops;
  }, [dirty, stops]);

  const startName = plan?.start?.name ?? plan?.start?.label ?? form?.start?.display ?? t("plan.start");
  const endName =
    plan?.end?.name ?? plan?.end?.label ?? (form && !form.endSame ? form.end?.display : null) ?? startName;
  const nameOf: Names = (ref) => {
    if (!ref || ref === "?") return "?";
    if (ref === "start") return startName;
    if (ref === "end") return endName;
    return stops.find((x) => x.place_id === ref)?.name ?? plan?.stops.find((x) => x.place_id === ref)?.name ?? ref;
  };
  const trip: Trip | null = form ? { date: form.date, depart: form.depart_time, arrive: form.return_time } : null;

  function cancel() {
    if (dirty && clean.current) onRestore(clean.current);
    setEditingFor(undefined);
  }

  return (
    <div className={s.layout} data-view={mapReady ? view : "timeline"}>
      <div className={s.head}>
        <p className={s.back}>
          <button type="button" className={ui.navLink} onClick={onBack}>
            <ArrowLeftIcon className={ui.arrowStart} />
            {t("plan.back")}
          </button>
        </p>
        <div className={s.titleRow}>
          <h2 className={s.title}>{t("plan.title")}</h2>
          {plan?.mode === "manual" && <span className={ui.chip}>{t("plan.manual")}</span>}
        </div>
        {form && <TripChips form={form} />}
      </div>

      <div className={s.main}>
        {(fresh || (!plan && loading && !dirty)) && (
          <div className={s.statusSlot}>
            {fresh && trip ? (
              <div className={appear}>
                <PlanStatus plan={plan} nameOf={nameOf} stops={stops} onStopsChange={onStopsChange} trip={trip} />
              </div>
            ) : (
              <SkeletonCard lines={2} />
            )}
          </div>
        )}
        {mapReady && (
          <ViewSwitch
            className={s.viewSwitch}
            label={t("plan.viewLabel")}
            value={view}
            onChange={setView}
            options={[
              { value: "timeline", label: t("plan.viewTimeline"), icon: <TimelineIcon /> },
              { value: "map", label: t("plan.viewMap"), icon: <MapIcon /> },
            ]}
          />
        )}
        <div className={s.timelineCol}>
          {editing ? (
            <StopEditor
              stops={stops}
              planStops={plan?.stops ?? []}
              dirty={dirty}
              busy={busy}
              loading={loading}
              canCancel={Boolean(plan)}
              onStopsChange={onStopsChange}
              onCheck={onCheck}
              onCancel={cancel}
            />
          ) : fresh ? (
            <div className={appear}>
              <Timeline
                items={plan.timeline}
                nameOf={nameOf}
                stops={plan.stops}
                returnBy={trip?.arrive}
                navHref={(to) => planLegUrl(plan, to, t("plan.navDestination"))}
                action={
                  <button type="button" className={`${ui.secondary} ${s.adjustBtn}`} onClick={() => setEditingFor(plan)}>
                    <PencilIcon size={16} />
                    {t("plan.adjust")}
                  </button>
                }
              />
            </div>
          ) : loading ? (
            <SkeletonCard lines={6} height={280} />
          ) : null}
        </div>
        {plan && (
          <div className={s.packingSlot}>
            <PlanPacking plan={plan} stops={stops} />
          </div>
        )}
      </div>

      <div className={s.aside}>
        {plan?.weather && trip && (
          <div className={s.weatherSlot}>
            <WeatherCard weather={plan.weather} date={trip.date} depart={trip.depart} arrive={trip.arrive} />
          </div>
        )}
        {mapReady ? (
          <div className={s.mapCol}>
            <MapPanel hints={plan?.map} scene={scene} legend="plan" />
          </div>
        ) : mapState === "locked" ? (
          <MapHint className={s.mapHint} />
        ) : null}
        <div className={s.support}>
          {fresh && <NavigationCard plan={plan} nameOf={nameOf} />}
          <section className={`${ui.card} ${s.saveCard}`} aria-labelledby="save-title">
            <h2 className={s.cardTitle} id="save-title">
              {t("plan.saveTitle")}
            </h2>
            <FavoriteButton plan={plan} stops={stops} dirty={dirty} busy={busy} />
            {plan && (
              <p className={s.footHint}>
                {t("feedback.planPrompt")}
                <Link className={ui.inlineNav} href="/feedback?from=planner">
                  {t("feedback.planLink")}
                  <ArrowRightIcon className={ui.arrowEnd} />
                </Link>
              </p>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

function StopEditor({
  stops,
  planStops,
  dirty,
  busy,
  loading,
  canCancel,
  onStopsChange,
  onCheck,
  onCancel,
}: {
  stops: EditStop[];
  planStops: PlanStop[];
  dirty: boolean;
  busy: boolean;
  loading: boolean;
  canCancel: boolean;
  onStopsChange: (stops: EditStop[]) => void;
  onCheck: () => void;
  onCancel: () => void;
}) {
  const t = useTranslations("plan");
  const listRef = useRef<HTMLOListElement>(null);
  const moved = useRef<{ id: string; dir: "up" | "down" } | null>(null);
  const [announce, setAnnounce] = useState("");
  const planStop = (id: string) => planStops.find((x) => x.place_id === id);

  useEffect(() => {
    const m = moved.current;
    if (!m) return;
    moved.current = null;
    const list = listRef.current;
    const same = list?.querySelector<HTMLButtonElement>(`[data-move="${m.dir}"][data-stop="${m.id}"]`);
    const other = list?.querySelector<HTMLButtonElement>(`[data-move="${m.dir === "up" ? "down" : "up"}"][data-stop="${m.id}"]`);
    (same && !same.disabled ? same : other)?.focus();
  }, [stops]);

  function move(i: number, d: -1 | 1) {
    const next = [...stops];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    moved.current = { id: stops[i].place_id, dir: d === -1 ? "up" : "down" };
    setAnnounce(t("movedTo", { name: stops[i].name, n: i + d + 1 }));
    onStopsChange(next);
  }

  return (
    <section className={`${ui.card} ${s.editor}`} aria-labelledby="stops-title">
      <h2 className={s.cardTitle} id="stops-title">
        {t("adjust")}
      </h2>
      <ol className={s.stops} ref={listRef}>
        {stops.map((st, i) => {
          const ps = planStop(st.place_id);
          const minutes = st.stay_minutes ?? ps?.stay_minutes ?? st.default_stay_minutes ?? null;
          return (
            <li key={st.place_id} className={s.stop}>
              <span className={s.badge} aria-hidden="true">
                {i + 1}
              </span>
              <div className={s.stopBody}>
                <strong className={s.stopName}>{st.name}</strong>
                <div className={s.stopMeta}>
                  <label className="visually-hidden" htmlFor={`stay-${st.place_id}`}>
                    {t("stayLabel", { name: st.name })}
                  </label>
                  <select
                    id={`stay-${st.place_id}`}
                    className={s.staySelect}
                    value={minutes ?? ""}
                    onChange={(e) =>
                      onStopsChange(stops.map((x, j) => (j === i ? { ...x, stay_minutes: Number(e.target.value) } : x)))
                    }
                  >
                    {minutes === null && <option value="">—</option>}
                    {STAY_OPTIONS.map((m) => (
                      <option key={m} value={m}>
                        {t("stayOption", { m })}
                      </option>
                    ))}
                  </select>
                  {ps?.hours && <HoursText hours={ps.hours} />}
                  {ps?.removed && <span className={ui.chipRed}>{t("removed")}</span>}
                </div>
              </div>
              <div className={s.stopActions}>
                <button
                  type="button"
                  className={`${s.stopBtn} ${s.stopMove}`}
                  data-move="up"
                  data-stop={st.place_id}
                  disabled={i === 0}
                  onClick={() => move(i, -1)}
                  aria-label={t("moveUp", { name: st.name })}
                >
                  <ChunkyUpIcon size={22} />
                </button>
                <button
                  type="button"
                  className={`${s.stopBtn} ${s.stopMove}`}
                  data-move="down"
                  data-stop={st.place_id}
                  disabled={i === stops.length - 1}
                  onClick={() => move(i, 1)}
                  aria-label={t("moveDown", { name: st.name })}
                >
                  <ChunkyDownIcon size={22} />
                </button>
                <button
                  type="button"
                  className={`${s.stopBtn} ${s.stopRemove}`}
                  disabled={stops.length <= 1}
                  onClick={() => onStopsChange(stops.filter((_, j) => j !== i))}
                  aria-label={t("remove", { name: st.name })}
                >
                  <ChunkyCloseIcon size={22} />
                </button>
              </div>
            </li>
          );
        })}
      </ol>
      <div className={s.editorFoot}>
        {dirty && (
          <p className={s.dirtyNote} role="status">
            <AlertIcon size={16} />
            {t("dirtyStatus")}
          </p>
        )}
        <div className={s.editorActions}>
          {dirty ? (
            <>
              {canCancel && (
                <button type="button" className={ui.secondary} onClick={onCancel} disabled={busy}>
                  {t("cancel")}
                </button>
              )}
              <button type="button" className={ui.primary} onClick={onCheck} disabled={busy} aria-busy={busy && !loading}>
                {busy && !loading ? t("checking") : t("check")}
              </button>
            </>
          ) : (
            <button type="button" className={ui.secondary} onClick={onCancel}>
              {t("done")}
            </button>
          )}
        </div>
      </div>
      <p className="visually-hidden" role="status">
        {announce}
      </p>
    </section>
  );
}

function HoursText({ hours }: { hours: Schemas["HoursOut"] }) {
  const t = useTranslations("plan");
  if (hours.status === "unknown") {
    return (
      <span className={s.warnText}>
        <AlertIcon size={14} />
        {t("hoursUnknown")}
      </span>
    );
  }
  if (hours.status === "closed_permanently" || hours.status === "closed_temporarily") {
    return <span className={s.dangerText}>{hours.notes[0] ?? hours.status}</span>;
  }
  const iv = hours.intervals
    .map(([a, b]) => {
      if (!a || !b) return null;
      const ms = new Date(b).getTime() - new Date(a).getTime();
      if (ms >= 24 * 3600 * 1000 - 60 * 1000) return "all";
      const nextDay = taipeiToday(new Date(b)) !== taipeiToday(new Date(a)) ? t("nextDay") : "";
      return `${formatClock(a)}–${nextDay}${formatClock(b)}`;
    })
    .filter((x): x is string => Boolean(x));
  if (iv.length === 0) return null;
  if (iv.includes("all")) return <span>{t("allDay")}</span>;
  return <span>{t("hours", { iv: iv.join("、") })}</span>;
}

function weatherLine(t: ReturnType<typeof useTranslations>, weather: Schemas["WeatherOut"] | null | undefined, trip: Trip): string | null {
  if (!weather) return null;
  const areas = weather.areas ?? [];
  const pct = (a: Schemas["WeatherAreaOut"]) => tripMax(a, trip.date, trip.depart, trip.arrive) ?? a.max_precipitation_percent ?? null;
  const areaName = (a: Schemas["WeatherAreaOut"]) =>
    a.label ?? t(a.roles.includes("start") ? "weather.nearStart" : a.roles.includes("end") ? "weather.nearEnd" : "weather.otherArea");
  if (weather.rain_filter) {
    const hit = areas.filter((a) => a.status === "triggered");
    if (hit.length > 0) return hit.map((a) => t("plan.weatherIndoor", { name: areaName(a), p: pct(a) ?? "—" })).join("；");
  }
  const start = areas.find((a) => a.roles.includes("start"));
  const p = start ? pct(start) : (weather.max_precipitation_percent ?? null);
  if (p === null) return weather.status === "unverified" || areas.length > 0 ? t("plan.weatherUnknown") : null;
  return t("plan.weatherOk", { p });
}

export function PlanStatus({
  plan,
  nameOf,
  stops,
  onStopsChange,
  trip,
  readOnly = false,
}: {
  plan: PlanResponse;
  nameOf: Names;
  stops: EditStop[];
  onStopsChange: (s: EditStop[]) => void;
  trip: Trip;
  readOnly?: boolean;
}) {
  const t = useTranslations();
  const f = plan.feasibility;
  const tone = f === "feasible" ? s.feasible : f === "infeasible" ? s.infeasible : s.unverified;
  const icon = f === "feasible" ? "✓" : f === "infeasible" ? "✕" : "?";
  const unknownHours = plan.stops.filter((x) => x.hours?.status === "unknown").map((x) => x.name ?? nameOf(x.place_id));
  const weather = weatherLine(t, plan.weather, trip);
  const lines: string[] = [
    ...(weather ? [weather] : []),
    ...(unknownHours.length > 0 ? [t("plan.hoursUnknownStops", { names: unknownHours.join("、") })] : []),
    ...plan.violations.map((v) => `${t(`violations.${v.code}`)}${v.place_ref ? `：${nameOf(v.place_ref)}` : ""}`),
    ...plan.warnings.filter((w) => KEEP_WARNINGS.has(w.code)).map((w) => w.message),
  ];
  if (f === "unverified" && lines.length === 0) lines.push(t("plan.unverifiedNote"));
  return (
    <section className={`${ui.card} ${s.status} ${tone}`} aria-live="polite">
      <div className={s.statusHead}>
        <span className={s.statusIcon} aria-hidden="true">
          {icon}
        </span>
        <div>
          <h2 className={s.statusTitle}>{t(`feasibility.${f}`)}</h2>
          {f === "infeasible" && <p className={s.statusDesc}>{t("feasibility.infeasibleDesc")}</p>}
        </div>
      </div>
      {lines.length > 0 && (
        <ul className={s.statusList}>
          {lines.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      )}
      {plan.suggest_remove.length > 0 && (
        <div className={s.block}>
          <p>{t("plan.suggestRemove", { names: plan.suggest_remove.map(nameOf).join("、") })}</p>
          {!readOnly && (
            <div className={s.suggest}>
              {plan.suggest_remove.map((id) => (
                <button
                  key={id}
                  type="button"
                  className={ui.soft}
                  disabled={stops.length <= 1}
                  onClick={() => onStopsChange(stops.filter((x) => x.place_id !== id))}
                >
                  {t("plan.removeSuggested", { name: nameOf(id) })}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function PlanPacking({ plan, stops }: { plan: PlanResponse; stops: EditStop[] }) {
  const { form } = usePlanner();
  if (!form) return null;
  const ages = form.children.filter((x): x is number => x !== null);
  const ids = new Set(stops.map((x) => x.place_id));
  return (
    <PackingList
      listId={queryListId(plan.query_id)}
      ages={ages}
      hasNap={form.nap.enabled}
      primaryTypes={plan.stops.filter((x) => ids.has(x.place_id)).map((x) => x.primary_type)}
      className={s.packing}
    />
  );
}

function NavigationCard({ plan, nameOf }: { plan: PlanResponse; nameOf: Names }) {
  const t = useTranslations("plan");
  const fallback = t("navDestination");
  const first = plan.timeline.find((x) => x.type === "move");
  const firstUrl = first ? planLegUrl(plan, first.to, fallback) : null;
  if (!firstUrl) return null;
  const route = routeUrl(plan.stops.map(placeTarget), endpointTarget(plan.end, fallback));
  return (
    <section className={`${ui.card} ${s.navCard}`} aria-labelledby="nav-title">
      <h2 className={s.cardTitle} id="nav-title">
        {t("navTitle")}
      </h2>
      <p className={s.navFirst}>{t("navFirst", { name: nameOf(first?.to) })}</p>
      <div className={s.navActions}>
        <NavLink className={ui.primary} href={firstUrl}>
          {t("navOpen")}
        </NavLink>
        {route && (
          <NavLink className={ui.soft} href={route}>
            {t("navRoute")}
          </NavLink>
        )}
      </div>
      <p className={s.footHint}>{t("navNote")}</p>
    </section>
  );
}

const minutesBetween = (a: string | null | undefined, b: string | null | undefined) =>
  a && b ? Math.round((new Date(b).getTime() - new Date(a).getTime()) / 60000) : null;


export function Timeline({
  items,
  nameOf,
  navHref,
  stops = [],
  returnBy,
  action,
}: {
  items: Schemas["TimelineItem"][];
  nameOf: Names;
  navHref?: (to: string | null | undefined) => string | null;
  stops?: PlanStop[];
  returnBy?: string;
  action?: ReactNode;
}) {
  const t = useTranslations("plan");
  const numbers: number[] = [];
  let count = 0;
  for (const it of items) {
    if (it.type === "attraction") count += 1;
    numbers.push(count);
  }
  const last = items[items.length - 1];
  const arrival = last?.end ? formatClock(last.end) : null;
  const diff = arrival && returnBy ? toMinutes(returnBy) - toMinutes(arrival) : null;
  const duration = (minutes: number) => {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return h && m ? t("hm", { h, m }) : h ? t("hOnly", { h }) : t("mOnly", { m });
  };
  return (
    <section className={ui.card} aria-labelledby="tl-title">
      <div className={s.tlHead}>
        <h2 className={s.cardTitle} id="tl-title">
          {t("timeline")}
        </h2>
        {action}
      </div>
      {items.length > 0 && (
      <ol className={s.timeline}>
        {items.map((it, i) => {
          const kind = it.type === "rest" && it.reason === "nap" ? "nap" : it.type;
          let mark: ReactNode;
          let body: ReactNode;
          if (it.type === "attraction") {
            const info = stops.find((x) => x.place_id === it.place_id);
            const minutes = info?.stay_minutes ?? minutesBetween(it.start, it.end);
            mark = <span className={s.tlNum}>{numbers[i]}</span>;
            body = (
              <>
                <span className={s.tlPlace}>
                  <PlaceArt type={info?.primary_type} className={s.tlArt} />
                  <span className={s.tlTitle}>{it.name ?? nameOf(it.place_id)}</span>
                </span>
                <span className={s.tlMeta}>
                  {minutes !== null && <span>{t("stay", { m: minutes })}</span>}
                  {info?.hours && <HoursText hours={info.hours} />}
                </span>
              </>
            );
          } else if (it.type === "move") {
            const legHref = navHref?.(it.to) ?? null;
            mark = <CarIcon size={16} />;
            body = (
              <>
                <span className={s.tlTitle}>
                  {nameOf(it.from)} → {nameOf(it.to)}
                </span>
                <span className={s.tlMeta}>
                  {it.duration_s != null ? (
                    <>
                      <span>{t("drive", { m: Math.max(1, Math.ceil(it.duration_s / 60)) })}</span>
                      {it.distance_m != null && <span>{(it.distance_m / 1000).toFixed(1)} km</span>}
                    </>
                  ) : (
                    <span>{t("driveUnknown")}</span>
                  )}
                  {legHref && (
                    <NavLink className={s.navLeg} href={legHref} label={t("navLegLabel", { name: nameOf(it.to) })}>
                      <NavigateIcon size={14} />
                      {t("navLeg")}
                    </NavLink>
                  )}
                </span>
              </>
            );
          } else {
            const title = it.type === "meal" ? (it.meal === "dinner" ? t("dinner") : t("lunch")) : it.reason === "nap" ? t("nap") : t("wait");
            mark = it.type === "meal" ? <MealIcon size={16} /> : it.reason === "nap" ? <MoonIcon size={16} /> : <ClockIcon size={16} />;
            body = (
              <>
                <span className={s.tlTitle}>{title}</span>
                {it.type === "meal" && it.note && <span className={s.tlMeta}>{it.note}</span>}
              </>
            );
          }
          return (
            <li key={i} className={`${s.tlItem} ${s[`tl_${kind}`]}`}>
              <span className={s.tlTime}>{formatClock(it.start)}</span>
              <span className={s.tlDot} aria-hidden="true">
                {mark}
              </span>
              <span className={s.tlBody}>{body}</span>
            </li>
          );
        })}
        {arrival && diff !== null && (
          <li className={`${s.tlItem} ${s.tl_arrive}`}>
            <span className={s.tlTime}>{arrival}</span>
            <span className={s.tlDot} aria-hidden="true">
              <FlagIcon size={16} />
            </span>
            <span className={s.tlBody}>
              <span className={s.tlTitle}>
                {diff > 0
                  ? t("arriveEarly", { name: nameOf("end"), diff: duration(diff) })
                  : diff < 0
                    ? t("arriveLate", { name: nameOf("end"), diff: duration(-diff) })
                    : t("arriveOnTime", { name: nameOf("end") })}
              </span>
            </span>
          </li>
        )}
      </ol>
      )}
    </section>
  );
}
