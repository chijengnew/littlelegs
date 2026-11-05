"use client";

import { useEffect, useMemo, useRef } from "react";
import { useTranslations } from "next-intl";
import { API_CONFIGURED } from "@/lib/api/client";
import { validateForm } from "@/lib/form";
import { candidateScene } from "@/lib/mapData";
import { useAuth } from "./AuthProvider";
import CandidateList from "./CandidateList";
import ConditionsForm from "./ConditionsForm";
import MapPanel, { useEndpointTitles } from "./MemberMap";
import PlanView from "./PlanView";
import { usePlanner, type Step } from "./PlannerProvider";
import { LodgingList, WeatherNotice } from "./SidePanels";
import { SkeletonCard, SkeletonLine, SkeletonList, fadeIn } from "./Skeleton";
import ui from "./ui.module.css";
import s from "./Planner.module.css";

export default function Planner() {
  const t = useTranslations();
  const auth = useAuth();
  const uid = auth.user?.uid ?? null;
  const {
    step, setStep, form, setForm, errors, setErrors, apiError, busy, queryId, cands, selection, plan, dirty,
    importing, importError, clearImportError, resuming, loading, blocked, searchCandidates, runPlan, toggle, editStops, editConditions, resetAll,
  } = usePlanner();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const titles = useEndpointTitles();
  const candScene = useMemo(
    () => (cands ? candidateScene(cands, selection.map((x) => x.place_id), titles) : null),
    [cands, selection, titles],
  );

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
              {apiError.traceId && <div className={s.trace}>trace: {apiError.traceId}</div>}
            </div>
          </div>
        )}
      </div>

      {step === "conditions" && (
        <div className={s.formLayout}>
          <div className={s.hero}>
            <h2 className={s.heroTitle}>{t("app.tagline")}</h2>
            <p className={s.heroText}>{t("app.intro")}</p>
          </div>
          <ConditionsForm
            key={uid ?? "guest"}
            value={form}
            onChange={(next) => {
              setForm(next);
              if (Object.keys(errors).length) setErrors(validateForm(next));
            }}
            errors={errors} onSubmit={searchCandidates} busy={blocked} />
        </div>
      )}

      {step === "candidates" && (
        <div className={s.candLayout}>
          <div className={s.candMain}>
            <div className={s.candHead}>
              <div>
                <h2 className={s.title}>{t("candidates.title")}</h2>
                {cands ? (
                  <p className={ui.hint}>{t("candidates.count", { n: cands.candidate_count })}</p>
                ) : (
                  <SkeletonLine width="12em" />
                )}
              </div>
              <button type="button" className={ui.secondary} onClick={editConditions}>
                {t("candidates.editConditions")}
              </button>
            </div>
            {!cands ? (
              <SkeletonList count={4} />
            ) : (
            <div className={fadeIn}>
            {cands.operation === "partial" && (
              <div className={ui.bannerWarn}>
                <span aria-hidden="true">!</span>
                {t("candidates.partial")}
              </div>
            )}
            <WeatherNotice weather={cands.weather} />
            {cands.candidates.length === 0 ? (
              <div className={`${ui.card} ${s.empty}`}>
                <strong>{t("candidates.empty")}</strong>
                <p className={ui.hint}>{t("candidates.emptyHint")}</p>
              </div>
            ) : (
              <CandidateList
                items={cands.candidates}
                selected={selection.map((x) => x.place_id)}
              onToggle={(c) => { if (!blocked) toggle(c); }}
              />
            )}
            {cands.notices.map((n) => (
              <p key={n} className={ui.hint}>
                ※ {n}
              </p>
            ))}
            </div>
            )}
          </div>
          <aside className={s.candSide}>
            {cands ? (
              <>
                <MapPanel hints={cands.map} scene={candScene} legend="candidates" />
                <LodgingList lodging={cands.lodging} />
              </>
            ) : (
              <>
                <SkeletonCard lines={2} height={180} />
                <SkeletonCard lines={3} />
              </>
            )}
          </aside>
          <div className={s.selectBar}>
            <div className={s.selectInfo} aria-live="polite">
              <strong>{t("candidates.selected", { n: selection.length })}</strong>
              <span className={ui.hint} style={{ margin: 0 }}>
                {selection.length === 0
                  ? t("candidates.sortHint")
                  : selection.length >= 5
                    ? t("candidates.maxReached")
                    : selection.map((x) => x.name).join("、")}
              </span>
            </div>
            <button
              type="button"
              className={ui.primary}
              disabled={selection.length === 0 || blocked}
              aria-busy={busy}
              onClick={() => runPlan("sort")}
            >
              {busy && !resuming && <span className={ui.spinner} aria-hidden="true" />}
              {t("candidates.sort")}
            </button>
          </div>
        </div>
      )}

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
          onCheck={() => runPlan("check")}
          onBack={() => setStep("candidates")}
        />
      )}

      {step === "conditions" && (cands || queryId) && (
        <p className={s.reset}>
          <button type="button" className={ui.ghost} onClick={resetAll}>
            清除條件重新開始
          </button>
        </p>
      )}
      </fieldset>
    </div>
  );
}
