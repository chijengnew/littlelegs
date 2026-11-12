"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import {
  CONDITION_STEPS,
  FACILITY_PREFS,
  LAST_CONDITION_STEP,
  TYPE_PREFS,
  type FieldKey,
  type FormErrors,
  type FormState,
  type WindowState,
} from "@/lib/form";
import { dateRange, formatMonthDay, timeOptions } from "@/lib/time";
import EndpointPicker from "./EndpointPicker";
import { ArrowLeftIcon, ArrowRightIcon, CheckIcon, CloseIcon, PlusIcon } from "./icons";
import ui from "./ui.module.css";
import s from "./ConditionsForm.module.css";

type Props = {
  value: FormState;
  onChange: (f: FormState) => void;
  errors: FormErrors;
  onSubmit: () => void;
  busy: boolean;
  step: number;
  returning?: boolean;
  showHome?: boolean;
  onNext: () => void;
  onBack: () => void;
  onJump: (step: number) => void;
};

export default function ConditionsForm({ value: f, onChange, errors, onSubmit, busy, step, returning = false, showHome = true, onNext, onBack, onJump }: Props) {
  const t = useTranslations();
  const formRef = useRef<HTMLFormElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const [tick, setTick] = useState(0);
  const seen = useRef({ step, tick });
  const msg = (x: string) => (t.has(x) ? t(x) : x);
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => onChange({ ...f, [k]: v });
  const { min, max } = dateRange();
  const current = CONDITION_STEPS[step];
  const last = step === LAST_CONDITION_STEP;
  const editing = returning && !last;
  const isDone = (i: number) => (editing ? i !== step && i < LAST_CONDITION_STEP : i < step);
  const err = (k: FieldKey) =>
    errors[k] ? (
      <p className={ui.error} id={`err-${k}`}>
        {msg(errors[k]!)}
      </p>
    ) : null;

  useEffect(() => {
    if (seen.current.step === step && seen.current.tick === tick) return;
    seen.current = { step, tick };
    const bad = formRef.current?.querySelector<HTMLElement>("[aria-invalid='true'] input, input[aria-invalid='true'], select[aria-invalid='true']");
    if (bad) {
      bad.focus();
      return;
    }
    window.scrollTo({ top: 0 });
    titleRef.current?.focus({ preventScroll: true });
  }, [step, tick]);

  function toggleIn<T extends string>(list: T[], v: T): T[] {
    return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
  }

  const ageText = (a: number | null) => (a === null ? "—" : a === 0 ? t("form.ageUnder1") : t("form.ageYears", { n: a }));

  return (
    <form
      ref={formRef}
      className={s.form}
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (busy) return;
        if (last) onSubmit();
        else onNext();
        setTick((n) => n + 1);
      }}
    >
      <div className={s.progress}>
        <p className={s.progressLabel}>
          {t("form.stepOf", { n: step + 1, total: CONDITION_STEPS.length })}
        </p>
        <ol className={s.progressList} aria-label={t("form.progressLabel")}>
          {CONDITION_STEPS.map((x, i) => (
            <li
              key={x.key}
              className={i === step ? s.progressCurrent : isDone(i) ? s.progressDone : s.progressUpcoming}
              aria-current={i === step ? "step" : undefined}
            >
              <span className={s.progressBar} aria-hidden="true" />
              <span className={s.progressName}>
                {isDone(i) && <CheckIcon size={14} className={s.progressCheck} />}
                {t(`form.steps.${x.key}.title`)}
                {isDone(i) && <span className="visually-hidden">{t("form.stepDone")}</span>}
              </span>
            </li>
          ))}
        </ol>
      </div>

      <section className={ui.card} aria-labelledby="cond-step-title">
        <div className={s.stepHead}>
          <h2 id="cond-step-title" className={s.stepTitle} tabIndex={-1} ref={titleRef}>
            {t(`form.steps.${current.key}.heading`)}
          </h2>
          {current.key !== "extras" && <span className={s.tagRequired}>{t("form.required")}</span>}
        </div>

        {current.key === "schedule" && (
          <>
            <div className={s.grid3}>
              <div>
                <label className={ui.label} htmlFor="f-date">
                  {t("form.date")}
                </label>
                <input
                  id="f-date"
                  type="date"
                  className={ui.input}
                  min={min}
                  max={max}
                  value={f.date}
                  aria-invalid={Boolean(errors.date)}
                  aria-describedby="err-date"
                  onChange={(e) => set("date", e.target.value)}
                />
                {err("date")}
              </div>
              <TimeSelect
                id="f-depart"
                label={t("form.departTime")}
                value={f.depart_time}
                invalid={Boolean(errors.depart_time)}
                onChange={(v) => set("depart_time", v)}
              />
              <TimeSelect
                id="f-return"
                label={t("form.returnTime")}
                value={f.return_time}
                invalid={Boolean(errors.return_time)}
                onChange={(v) => set("return_time", v)}
              />
            </div>
            {err("depart_time")}
            {err("return_time")}
          </>
        )}

        {current.key === "route" && (
          <div className={s.stack}>
            <EndpointPicker
              label={t("form.start")}
              value={f.start}
              onChange={(v) => set("start", v)}
              error={errors.start}
            />
            <label className={s.check}>
              <input
                type="checkbox"
                checked={f.endSame}
                onChange={(e) => onChange({ ...f, endSame: e.target.checked, end: e.target.checked ? null : f.end })}
              />
              {t("form.endSameAsStart")}
            </label>
            {!f.endSame && (
              <EndpointPicker label={t("form.end")} value={f.end} onChange={(v) => set("end", v)} error={errors.end} />
            )}
          </div>
        )}

        {current.key === "children" && (
          <fieldset className={s.fieldset}>
            <legend className={ui.label}>{t("form.children")}</legend>
            <div className={s.children}>
              {f.children.map((age, i) => (
                <div key={i} className={s.child}>
                  <label className="visually-hidden" htmlFor={`f-age-${i}`}>
                    {t("form.childAge", { n: i + 1 })}
                  </label>
                  <select
                    id={`f-age-${i}`}
                    className={ui.input}
                    value={age ?? ""}
                    aria-invalid={Boolean(errors.children) && age === null}
                    onChange={(e) => {
                      const next = [...f.children];
                      next[i] = e.target.value === "" ? null : Number(e.target.value);
                      set("children", next);
                    }}
                  >
                    <option value="">—</option>
                    {Array.from({ length: 19 }, (_, a) => (
                      <option key={a} value={a}>
                        {ageText(a)}
                      </option>
                    ))}
                  </select>
                  {f.children.length > 1 && (
                    <button
                      type="button"
                      className={ui.icon}
                      aria-label={t("form.removeChild", { n: i + 1 })}
                      onClick={() => set("children", f.children.filter((_, j) => j !== i))}
                    >
                      <CloseIcon />
                    </button>
                  )}
                </div>
              ))}
              {f.children.length < 5 && (
                <button type="button" className={ui.soft} onClick={() => set("children", [...f.children, null])}>
                  <PlusIcon />
                  {t("form.addChild")}
                </button>
              )}
            </div>
            {err("children")}
          </fieldset>
        )}

        {current.key === "extras" && (
          <>
            <div className={s.windows}>
              <WindowField
                name="nap"
                label={t("form.nap")}
                value={f.nap}
                onChange={(v) => set("nap", v)}
                error={errors.nap && msg(errors.nap)}
              />
              <WindowField
                name="lunch"
                label={t("form.lunch")}
                value={f.lunch}
                onChange={(v) => set("lunch", v)}
                error={errors.lunch && msg(errors.lunch)}
              />
              <WindowField
                name="dinner"
                label={t("form.dinner")}
                value={f.dinner}
                onChange={(v) => set("dinner", v)}
                error={errors.dinner && msg(errors.dinner)}
              />
            </div>
            <hr className={s.hr} />
            <label className={s.switchRow}>
              <span className={s.switchTitle}>{t("form.rain")}</span>
              <input
                type="checkbox"
                role="switch"
                className={s.switch}
                checked={f.rain_indoor_only}
                onChange={(e) => set("rain_indoor_only", e.target.checked)}
              />
            </label>
            <hr className={s.hr} />
            <fieldset className={s.fieldset}>
              <legend className={ui.label}>{t("form.facilities")}</legend>
              <div className={s.chips}>
                {FACILITY_PREFS.map((k) => (
                  <label key={k} className={ui.toggle}>
                    <input
                      type="checkbox"
                      checked={f.facility_prefs.includes(k)}
                      onChange={() => set("facility_prefs", toggleIn(f.facility_prefs, k))}
                    />
                    {t(`facilities.${k}`)}
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset className={`${s.fieldset} ${s.fieldsetNext}`}>
              <legend className={ui.label}>{t("form.types")}</legend>
              <div className={s.chips}>
                {TYPE_PREFS.map((k) => (
                  <label key={k} className={ui.toggle}>
                    <input
                      type="checkbox"
                      checked={f.type_prefs.includes(k)}
                      onChange={() => set("type_prefs", toggleIn(f.type_prefs, k))}
                    />
                    {t(`types.${k}`)}
                  </label>
                ))}
              </div>
            </fieldset>
          </>
        )}
      </section>

      {last && (
        <section className={`${ui.card} ${s.summary}`} aria-labelledby="cond-summary-title">
          <h2 id="cond-summary-title" className={s.summaryTitle}>{t("form.summaryTitle")}</h2>
          <dl className={s.summaryList}>
            <SummaryRow
              label={t("form.steps.schedule.title")}
              value={`${formatMonthDay(f.date)} ${f.depart_time}–${f.return_time}`}
              action={t("form.editStep", { name: t("form.steps.schedule.title") })}
              text={t("form.edit")}
              onEdit={() => onJump(0)}
            />
            <SummaryRow
              label={t("form.steps.route.title")}
              value={`${f.start?.display ?? "—"} → ${f.endSame ? t("form.summaryEndSame") : (f.end?.display ?? "—")}`}
              action={t("form.editStep", { name: t("form.steps.route.title") })}
              text={t("form.edit")}
              onEdit={() => onJump(1)}
            />
            <SummaryRow
              label={t("form.steps.children.title")}
              value={f.children.map(ageText).join("、")}
              action={t("form.editStep", { name: t("form.steps.children.title") })}
              text={t("form.edit")}
              onEdit={() => onJump(2)}
            />
          </dl>
        </section>
      )}

      <div className={s.submitBar}>
        {last && (
          <p className={s.privacy}>
            {t("form.privacyNotice")} <Link href="/privacy">{t("form.privacyLink")}</Link>
          </p>
        )}
        <div className={s.navRow}>
          {step === 0 && !editing && showHome && (
            <Link href="/" className={`${ui.secondary} ${ui.large}`}>
              <ArrowLeftIcon className={ui.arrowStart} />
              {t("form.home")}
            </Link>
          )}
          {step > 0 && !editing && (
            <button type="button" className={`${ui.secondary} ${ui.large}`} onClick={onBack} disabled={busy}>
              <ArrowLeftIcon className={ui.arrowStart} />
              {t("form.back")}
            </button>
          )}
          <button type="submit" className={`${ui.primary} ${ui.large} ${s.grow}`} disabled={busy} aria-busy={busy}>
            {last ? (busy ? t("form.searching") : t("form.submit")) : editing ? t("form.done") : t("form.next")}
            {!last && !editing && <ArrowRightIcon className={ui.arrowEnd} />}
          </button>
        </div>
      </div>
    </form>
  );
}

function SummaryRow({ label, value, action, text, onEdit }: { label: string; value: string; action: string; text: string; onEdit: () => void }) {
  return (
    <div className={s.summaryRow}>
      <dt>{label}</dt>
      <dd>{value}</dd>
      <dd className={s.summaryAction}>
        <button type="button" className={ui.ghost} onClick={onEdit} aria-label={action}>
          <span aria-hidden="true">{text}</span>
        </button>
      </dd>
    </div>
  );
}

function TimeSelect(props: {
  id: string;
  label: string;
  value: string;
  invalid?: boolean;
  onChange: (v: string) => void;
  compact?: boolean;
}) {
  return (
    <div>
      <label className={props.compact ? ui.hint : ui.label} htmlFor={props.id}>
        {props.label}
      </label>
      <select
        id={props.id}
        className={ui.input}
        value={props.value}
        aria-invalid={props.invalid}
        onChange={(e) => props.onChange(e.target.value)}
      >
        {timeOptions(props.value).map((x) => (
          <option key={x} value={x}>
            {x}
          </option>
        ))}
      </select>
    </div>
  );
}

function WindowField(props: {
  name: string;
  label: string;
  value: WindowState;
  onChange: (v: WindowState) => void;
  error?: string;
}) {
  const t = useTranslations("form");
  const { value: w } = props;
  return (
    <div className={s.window}>
      <label className={s.check}>
        <input type="checkbox" checked={w.enabled} onChange={(e) => props.onChange({ ...w, enabled: e.target.checked })} />
        <strong>{props.label}</strong>
      </label>
      {w.enabled && (
        <div className={s.grid2}>
          <TimeSelect
            compact
            id={`f-${props.name}-s`}
            label={t("windowFrom")}
            value={w.start}
            invalid={Boolean(props.error)}
            onChange={(v) => props.onChange({ ...w, start: v })}
          />
          <TimeSelect
            compact
            id={`f-${props.name}-e`}
            label={t("windowTo")}
            value={w.end}
            invalid={Boolean(props.error)}
            onChange={(v) => props.onChange({ ...w, end: v })}
          />
        </div>
      )}
      {props.error && <p className={ui.error}>{props.error}</p>}
    </div>
  );
}
