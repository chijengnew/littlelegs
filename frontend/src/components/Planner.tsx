"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { API_CONFIGURED } from "@/lib/api/client";
import { stepErrors, validateForm } from "@/lib/form";
import { tripMax } from "@/lib/weather";
import { candidateScene } from "@/lib/mapData";
import { useAuth } from "./AuthProvider";
import CandidateList from "./CandidateList";
import ConditionsForm from "./ConditionsForm";
import MapPanel, { mapStateOf, useEndpointTitles } from "./MemberMap";
import PlanView from "./PlanView";
import { usePlanner, type Step } from "./PlannerProvider";
import SelectionBar from "./SelectionBar";
import StatePanel from "./StatePanel";
import { LodgingList, WeatherCard } from "./SidePanels";
import Mascot from "./art/Mascot";
import TripChips from "./TripChips";
import ViewSwitch from "./ViewSwitch";
import { ListIcon, MapIcon, PencilIcon } from "./icons";
import { SkeletonCard, SkeletonList, fadeIn } from "./Skeleton";
import ui from "./ui.module.css";
import s from "./Planner.module.css";

export default function Planner() {
  const t = useTranslations();
  const auth = useAuth();
  const uid = auth.user?.uid ?? null;
  const {
    step, setStep, form, errors, setErrors, apiError, busy, cands, selection, plan, dirty,
    importing, importError, clearImportError, resuming, loading, blocked, searchCandidates, runPlan, toggle, editStops, restoreStops, editConditions, resetAll,
    attach, conditionStep, returnToSummary, nextConditionStep, prevConditionStep, jumpConditionStep, inProgress, editForm,
  } = usePlanner();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [candView, setCandView] = useState<"list" | "map">("list");
  const [limitHit, setLimitHit] = useState(false);
  const [fromEdit, setFromEdit] = useState(false);
  useLayoutEffect(() => () => setFromEdit(false), []);
  const restart = () => {
    setFromEdit(true);
    editConditions();
  };
  const titles = useEndpointTitles();
  const candScene = useMemo(
    () => (cands ? candidateScene(cands, selection.map((x) => x.place_id), titles) : null),
    [cands, selection, titles],
  );
  const types = useMemo(
    () => Object.fromEntries((cands?.candidates ?? []).map((c) => [c.place_id, c.primary_type])),
    [cands],
  );
  const mapState = mapStateOf(Boolean(auth.member), cands?.map);

  useEffect(() => attach(), [attach]);

  useEffect(() => {
    headingRef.current?.focus();
    window.scrollTo({ top: 0 });
  }, [step]);

  if (loading || !form) {
    return (
      <div className={s.wrap} aria-busy="true">
        <SkeletonCard lines={6} height={420} />
      </div>
    );
  }

  const steps: { key: Step; label: string }[] = [
    { key: "conditions", label: t("steps.conditions") },
    { key: "candidates", label: t("steps.candidates") },
    { key: "plan", label: t("steps.plan") },
  ];
  const current = steps.findIndex((x) => x.key === step);

  return (
    <div className={s.wrap}>
      {!API_CONFIGURED && <p className={ui.bannerWarn} role="status">{t("errors.notConnected")}</p>}
      {auth.error && <p className={ui.bannerInfo} role="status">{t("auth.waitForVerification")}</p>}
      <p className="visually-hidden" role="status">
        {importing ? t("auth.importing") : resuming ? t("candidates.resuming") : ""}
      </p>
      {importError && <div className={ui.bannerError} role="alert"><span>{importError.message}</span>
        <button type="button" className={ui.soft} onClick={clearImportError}>{t("errors.retry")}</button>
        <button type="button" className={ui.soft} onClick={resetAll}>{t("auth.newQuery")}</button></div>}
      <fieldset disabled={!auth.ready || busy || importing} className={s.flow}>
      <div className={s.stepper}>
        <ol aria-label={t("steps.label")}>
          {steps.map((x, i) => (
            <li
              key={x.key}
              className={i === current ? s.stepActive : i < current ? s.step : s.stepUpcoming}
              aria-current={i === current ? "step" : undefined}
            >
              <span className={s.stepNum}>{i + 1}</span>
              <span>{x.label}</span>
            </li>
          ))}
        </ol>
      </div>

      <h1 className="visually-hidden" tabIndex={-1} ref={headingRef}>
        {steps.find((x) => x.key === step)?.label}
      </h1>

      <div aria-live="assertive">
        {apiError && (
          <div className={ui.bannerError} role="alert">
            <span aria-hidden="true">!</span>
            <div>
              <div>{apiError.message}</div>
              {apiError.fieldErrors.length > 0 && (
                <ul className={s.errList}>
                  {apiError.fieldErrors.map((e, i) => (
                    <li key={i}>{e.msg}</li>
                  ))}
                </ul>
              )}
              {apiError.traceId && <div className={s.trace}>{t("errors.traceId", { id: apiError.traceId })}</div>}
            </div>
          </div>
        )}
      </div>

      {step === "conditions" && (
        <div className={s.formLayout}>
          <ConditionsForm
            key={uid ?? "guest"}
            showHome={!fromEdit}
            value={form}
            onChange={(next) => {
              editForm(next);
              if (Object.keys(errors).length) setErrors(stepErrors(validateForm(next), conditionStep));
            }}
            errors={errors} onSubmit={searchCandidates} busy={blocked}
            step={conditionStep} returning={returnToSummary} onNext={nextConditionStep} onBack={prevConditionStep} onJump={jumpConditionStep} />
        </div>
      )}

      {step === "candidates" && (() => {
        const member = Boolean(auth.member);
        const weather = cands?.weather ?? null;
        const rain: Record<string, number | null> = {};
        for (const x of cands?.candidates ?? []) {
          const a = x.weather_area == null ? undefined : weather?.areas?.[x.weather_area];
          rain[x.place_id] = a ? tripMax(a, form.date, form.depart_time, form.return_time) : null;
        }
        const pick = (id: string) => {
          const c = cands?.candidates.find((x) => x.place_id === id);
          if (c && !blocked) {
            setLimitHit(false);
            toggle(c);
          }
        };
        return (
          <div className={s.candLayout} data-view={mapState === "ready" ? candView : "list"}>
            <div className={s.candTop}>
              <div className={s.candHead}>
                <div className={s.candHeadMain}>
                  <div className={s.candTitleRow}>
                    <span className={s.candArt}>
                      <Mascot size={48} />
                    </span>
                    <h2 className={s.title}>{t("candidates.title")}</h2>
                  </div>
                  <TripChips form={form} />
                </div>
              </div>
              {cands && cands.operation === "partial" && (
                <div className={ui.bannerWarn}>
                  <span aria-hidden="true">!</span>
                  {t("candidates.partial")}
                </div>
              )}
              {mapState === "ready" && (
                <ViewSwitch
                  className={s.candSwitch}
                  label={t("candidates.viewLabel")}
                  value={candView}
                  onChange={setCandView}
                  options={[
                    { value: "list", label: t("candidates.viewList"), icon: <ListIcon /> },
                    { value: "map", label: t("candidates.viewMap"), icon: <MapIcon /> },
                  ]}
                />
              )}
            </div>

            <div className={s.candAside}>
              <div className={s.candEditSlot}>
                <button type="button" className={`${ui.btn} ${s.candEdit}`} onClick={restart}>
                  <PencilIcon size={16} />
                  {t("candidates.editConditions")}
                </button>
              </div>
              {weather && form.date && (
                <div className={s.candWeather}>
                  <WeatherCard weather={weather} date={form.date} depart={form.depart_time} arrive={form.return_time} />
                </div>
              )}
              {member && mapState === "ready" && (
                <div className={s.candMap}>
                  {cands ? (
                    <MapPanel hints={cands.map} scene={candScene} legend="candidates" />
                  ) : (
                    <SkeletonCard lines={2} height={220} />
                  )}
                </div>
              )}
              <div className={s.candLodging}>
                {cands ? <LodgingList lodging={cands.lodging} /> : <SkeletonCard lines={2} />}
              </div>
            </div>

            <div className={s.candMain}>
              <section className={s.candList} aria-label={t("candidates.listLabel")}>
                {!cands ? (
                  <SkeletonList count={4} />
                ) : (
                  <div className={fadeIn}>
                    {cands.candidates.length === 0 ? (
                      <StatePanel
                        tone="empty"
                        inline
                        title={t("candidates.empty")}
                        description={<p>{t("candidates.emptyHint")}</p>}
                        actions={
                          <button type="button" className={ui.primary} onClick={restart}>
                            {t("candidates.editConditions")}
                          </button>
                        }
                      />
                    ) : (
                      <CandidateList
                        items={cands.candidates}
                        selected={selection.map((x) => x.place_id)}
                        onToggle={(c) => pick(c.place_id)}
                        onLimit={() => setLimitHit(true)}
                        rain={rain}
                        rainLimit={weather?.threshold_percent}
                      />
                    )}
                  </div>
                )}
              </section>
            </div>

            <div className={s.candBar}>
              <SelectionBar
                selection={selection}
                types={types}
                busy={blocked}
                sorting={busy && !resuming}
                limitHit={limitHit && selection.length >= 5}
                onRemove={pick}
                onSort={() => runPlan("sort")}
              />
            </div>
          </div>
        );
      })()}

      {step === "plan" && (
        <PlanView
          plan={plan}
          stops={selection}
          dirty={dirty}
          busy={blocked}
          loading={resuming}
          onStopsChange={(next) => {
            if (!blocked) editStops(next);
          }}
          onRestore={restoreStops}
          onCheck={() => runPlan("check")}
          onBack={() => setStep("candidates")}
        />
      )}

      {step === "conditions" && inProgress && (
        <p className={s.reset}>
          <button type="button" className={`${ui.ghost} ${s.resetBtn}`} onClick={resetAll}>
            {t("planner.resetAll")}
          </button>
        </p>
      )}
      </fieldset>
    </div>
  );
}
