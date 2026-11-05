"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { PlanResponse, Schemas } from "@/lib/api/client";
import FavoriteButton from "./FavoriteButton";
import { planScene } from "@/lib/mapData";
import { endpointTarget, planLegUrl, placeTarget, routeUrl } from "@/lib/mapsUrl";
import { queryListId } from "@/lib/packingStorage";
import { formatClock, taipeiToday } from "@/lib/time";
import MapPanel, { useEndpointTitles } from "./MemberMap";
import NavLink from "./NavLink";
import PackingList from "./PackingList";
import { usePlanner } from "./PlannerProvider";
import { WeatherNotice } from "./SidePanels";
import { SkeletonCard, appear } from "./Skeleton";
import ui from "./ui.module.css";
import s from "./PlanView.module.css";

export type EditStop = { place_id: string; name: string; stay_minutes: number | null; default_stay_minutes?: number };

type Props = {
  plan: PlanResponse | null;
  stops: EditStop[];
  dirty: boolean;
  busy: boolean;
  loading?: boolean;
  onStopsChange: (stops: EditStop[]) => void;
  onCheck: () => void;
  onBack: () => void;
};

const STAY_OPTIONS = Array.from({ length: 24 }, (_, i) => (i + 1) * 15);

export default function PlanView({ plan, stops, dirty, busy, loading = false, onStopsChange, onCheck, onBack }: Props) {
  const t = useTranslations();
  const titles = useEndpointTitles();
  const scene = useMemo(() => (plan ? planScene(plan, stops.map((x) => x.place_id), titles) : null), [plan, stops, titles]);
  const planStop = (id: string) => plan?.stops.find((x) => x.place_id === id);
  const nameOf = (ref: string | null | undefined) => {
    if (!ref || ref === "?") return "?";
    if (ref === "start") return t("plan.start");
    if (ref === "end") return t("plan.end");
    return stops.find((x) => x.place_id === ref)?.name ?? planStop(ref)?.name ?? ref;
  };

  function move(i: number, d: -1 | 1) {
    const next = [...stops];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    onStopsChange(next);
  }

  return (
    <div className={s.layout}>
      <div className={s.main}>
        {plan && !dirty && (
          <div className={appear}>
            <FeasibilityCard plan={plan} nameOf={nameOf} stops={stops} onStopsChange={onStopsChange} />
          </div>
        )}
        {!plan && loading && !dirty && <SkeletonCard lines={2} />}
        {dirty && (
          <div className={ui.bannerInfo} role="status">
            <span aria-hidden="true">✎</span>
            <span>{t("plan.dirty")}</span>
          </div>
        )}

        <section className={ui.card} aria-labelledby="stops-title">
          <div className={s.sectionHead}>
            <h2 className={ui.cardTitle} id="stops-title" style={{ margin: 0 }}>
              {t("plan.stopsTitle")}
            </h2>
            {plan && (
              <span className={ui.chip}>{plan.mode === "auto" ? t("plan.modeAuto") : t("plan.modeManual")}</span>
            )}
          </div>
          <ol className={s.stops}>
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
                        {t("plan.stayLabel", { name: st.name })}
                      </label>
                      <select
                        id={`stay-${st.place_id}`}
                        className={s.staySelect}
                        value={minutes ?? ""}
                        onChange={(e) =>
                          onStopsChange(
                            stops.map((x, j) => (j === i ? { ...x, stay_minutes: Number(e.target.value) } : x)),
                          )
                        }
                      >
                        {minutes === null && <option value="">—</option>}
                        {STAY_OPTIONS.map((m) => (
                          <option key={m} value={m}>
                            {m} 分鐘
                          </option>
                        ))}
                      </select>
                      {st.stay_minutes === null && ps?.estimated && <span className={ui.chip}>{t("plan.estimated")}</span>}
                      {ps?.hours && <HoursChip hours={ps.hours} />}
                      {ps?.removed && <span className={ui.chipRed}>{t("plan.removed")}</span>}
                    </div>
                  </div>
                  <div className={s.stopActions}>
                    <button
                      type="button"
                      className={ui.icon}
                      disabled={i === 0}
                      onClick={() => move(i, -1)}
                      aria-label={t("plan.moveUp", { name: st.name })}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className={ui.icon}
                      disabled={i === stops.length - 1}
                      onClick={() => move(i, 1)}
                      aria-label={t("plan.moveDown", { name: st.name })}
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      className={ui.icon}
                      disabled={stops.length <= 1}
                      onClick={() => onStopsChange(stops.filter((_, j) => j !== i))}
                      aria-label={t("plan.remove", { name: st.name })}
                    >
                      ×
                    </button>
                  </div>
                </li>
              );
            })}
          </ol>
          <p className={ui.hint}>{t("plan.stayHint")}</p>
        </section>

        {plan && !dirty && (
          <div className={appear}>
            <NavigationCard plan={plan} nameOf={nameOf} />
            <Timeline
              items={plan.timeline}
              nameOf={nameOf}
              navHref={(to) => planLegUrl(plan, to, t("plan.navDestination"))}
            />
          </div>
        )}
        {!plan && loading && !dirty && <SkeletonCard lines={6} height={280} />}
        {plan && <PlanPacking plan={plan} stops={stops} />}
        {plan && (
          <p className={ui.hint}>
            {t("feedback.planPrompt")} <Link href="/feedback?from=planner">{t("feedback.planLink")}</Link>
          </p>
        )}
      </div>

      <aside className={s.side}>
        {plan?.weather && <WeatherNotice weather={plan.weather} />}
        <MapPanel hints={plan?.map} scene={scene} legend="plan" />
        {plan && plan.notices.length > 0 && (
          <div className={ui.bannerWarn}>
            <span aria-hidden="true">!</span>
            <ul className={s.plainList}>
              {plan.notices.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </div>
        )}
        <FavoriteButton plan={plan} stops={stops} dirty={dirty} busy={busy} />
      </aside>

      <div className={s.actionBar}>
        <button type="button" className={ui.secondary} onClick={onBack}>
          ← {t("plan.back")}
        </button>
        <button type="button" className={`${ui.primary} ${s.grow}`} onClick={onCheck} disabled={busy} aria-busy={busy}>
          {busy && !loading && <span className={ui.spinner} aria-hidden="true" />}
          {busy && !loading ? t("plan.checking") : t("plan.check")}
        </button>
      </div>
    </div>
  );
}

function HoursChip({ hours }: { hours: Schemas["HoursOut"] }) {
  const t = useTranslations("plan");
  if (hours.status === "unknown") return <span className={ui.chipAmber}>{t("hoursUnknown")}</span>;
  if (hours.status === "provisional") return <span className={ui.chipAmber}>{t("hoursProvisional")}</span>;
  if (hours.status === "closed_permanently" || hours.status === "closed_temporarily")
    return <span className={ui.chipRed}>{hours.notes[0] ?? hours.status}</span>;
  const iv = hours.intervals
    .map(([a, b]) => {
      if (!a || !b) return null;
      const ms = new Date(b).getTime() - new Date(a).getTime();
      if (ms >= 24 * 3600 * 1000 - 60 * 1000) return t("allDay");
      const nextDay = taipeiToday(new Date(b)) !== taipeiToday(new Date(a)) ? t("nextDay") : "";
      return `${formatClock(a)}–${nextDay}${formatClock(b)}`;
    })
    .filter(Boolean)
    .join("、");
  return iv ? <span className={ui.chip}>{t("hours", { iv })}</span> : null;
}

export function FeasibilityCard({
  plan,
  nameOf,
  stops,
  onStopsChange,
  readOnly = false,
}: {
  plan: PlanResponse;
  nameOf: (ref: string | null | undefined) => string;
  stops: EditStop[];
  onStopsChange: (s: EditStop[]) => void;
  readOnly?: boolean;
}) {
  const t = useTranslations();
  const f = plan.feasibility;
  const tone = f === "feasible" ? s.feasible : f === "infeasible" ? s.infeasible : s.unverified;
  const icon = f === "feasible" ? "✓" : f === "infeasible" ? "✕" : "?";
  return (
    <section className={`${ui.card} ${s.feas} ${tone}`} aria-live="polite">
      <div className={s.feasHead}>
        <span className={s.feasIcon} aria-hidden="true">
          {icon}
        </span>
        <div>
          <h2 className={s.feasTitle}>{t(`feasibility.${f}`)}</h2>
          <p className={s.feasDesc}>{plan.feasibility_note || t(`feasibility.${f}Desc`)}</p>
        </div>
      </div>
      <p className={ui.hint}>
        {plan.mode === "manual"
          ? t("plan.notOptimal")
          : plan.search.complete
            ? t("plan.optimalNote", { n: plan.search.permutations_evaluated })
            : t("plan.searchIncomplete")}
      </p>

      {plan.violations.length > 0 && (
        <div className={s.block}>
          <h3 className={s.blockTitle}>{t("plan.violations")}</h3>
          <ul className={s.plainList}>
            {plan.violations.map((v, i) => (
              <li key={i}>
                {t(`violations.${v.code}`)}
                {v.place_ref && `：${nameOf(v.place_ref)}`}
              </li>
            ))}
          </ul>
        </div>
      )}

      {plan.suggest_remove.length > 0 && (
        <div className={s.block}>
          <p>{t("plan.suggestRemove", { names: plan.suggest_remove.map(nameOf).join("、") })}</p>
          {!readOnly && <div className={s.suggest}>
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
          </div>}
        </div>
      )}

      {plan.warnings.length > 0 && (
        <div className={s.block}>
          <h3 className={s.blockTitle}>{t("plan.warnings")}</h3>
          <ul className={s.plainList}>
            {plan.warnings.map((w, i) => (
              <li key={`${w.code}-${i}`}>{w.message}</li>
            ))}
          </ul>
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
    />
  );
}

function NavigationCard({ plan, nameOf }: { plan: PlanResponse; nameOf: (ref: string | null | undefined) => string }) {
  const t = useTranslations("plan");
  const fallback = t("navDestination");
  const first = plan.timeline.find((x) => x.type === "move");
  const firstUrl = first ? planLegUrl(plan, first.to, fallback) : null;
  if (!firstUrl) return null;
  const route = routeUrl(plan.stops.map(placeTarget), endpointTarget(plan.end, fallback));
  return (
    <section className={`${ui.card} ${s.navCard}`} aria-labelledby="nav-title">
      <h2 className={ui.cardTitle} id="nav-title">
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
      <p className={ui.hint} style={{ margin: 0 }}>
        {t("navNote")}
      </p>
    </section>
  );
}

export function Timeline({
  items,
  nameOf,
  navHref,
}: {
  items: Schemas["TimelineItem"][];
  nameOf: (ref: string | null | undefined) => string;
  navHref?: (to: string | null | undefined) => string | null;
}) {
  const t = useTranslations("plan");
  return (
    <section className={ui.card} aria-labelledby="tl-title">
      <h2 className={ui.cardTitle} id="tl-title">
        {t("timeline")}
      </h2>
      <ol className={s.timeline}>
        {items.map((it, i) => {
          let title: string;
          let sub: string | null = null;
          if (it.type === "attraction") title = it.name ?? nameOf(it.place_id);
          else if (it.type === "meal") {
            title = it.meal === "dinner" ? t("dinner") : t("lunch");
            sub = it.note ?? null;
          } else if (it.type === "move") {
            title = `${nameOf(it.from)} → ${nameOf(it.to)}`;
            sub =
              it.duration_s != null
                ? `${t("drive", { m: Math.max(1, Math.ceil(it.duration_s / 60)) })}${it.distance_m != null ? `・${(it.distance_m / 1000).toFixed(1)} km` : ""}`
                : t("driveUnknown");
          } else {
            title = it.reason === "nap" ? t("nap") : t("wait");
            sub = it.note ?? null;
          }
          const legHref = it.type === "move" ? (navHref?.(it.to) ?? null) : null;
          return (
            <li key={i} className={`${s.tlItem} ${s[`tl_${it.type}`]}`}>
              <span className={s.tlTime}>
                {formatClock(it.start)}
                <span className={s.tlEnd}>–{formatClock(it.end)}</span>
              </span>
              <span className={s.tlDot} aria-hidden="true" />
              <span className={s.tlBody}>
                <span className={s.tlTitle}>{title}</span>
                {sub && <span className={s.tlSub}>{sub}</span>}
                {it.estimated && <span className={ui.chip}>{t("estimated")}</span>}
                {legHref && (
                  <NavLink className={s.navLeg} href={legHref} label={t("navLegLabel", { name: nameOf(it.to) })}>
                    {t("navLeg")}
                  </NavLink>
                )}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
