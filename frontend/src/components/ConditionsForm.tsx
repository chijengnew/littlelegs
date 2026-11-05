"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import {
  FACILITY_PREFS,
  TYPE_PREFS,
  type FieldKey,
  type FormErrors,
  type FormState,
  type WindowState,
} from "@/lib/form";
import { QUARTER_TIMES, dateRange, formatDateLabel } from "@/lib/time";
import EndpointPicker from "./EndpointPicker";
import ui from "./ui.module.css";
import s from "./ConditionsForm.module.css";

type Props = {
  value: FormState;
  onChange: (f: FormState) => void;
  errors: FormErrors;
  onSubmit: () => void;
  busy: boolean;
};

export default function ConditionsForm({ value: f, onChange, errors, onSubmit, busy }: Props) {
  const t = useTranslations();
  const msg = (x: string) => (t.has(x) ? t(x) : x);
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => onChange({ ...f, [k]: v });
  const { min, max } = dateRange();
  const err = (k: FieldKey) =>
    errors[k] ? (
      <p className={ui.error} id={`err-${k}`}>
        {msg(errors[k]!)}
      </p>
    ) : null;

  function toggleIn<T extends string>(list: T[], v: T): T[] {
    return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
  }

  return (
    <form
      className={s.form}
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (!busy) onSubmit();
      }}
    >
      <section className={ui.card}>
        <h2 className={ui.cardTitle}>{t("form.title")}</h2>
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
            {errors.date ? err("date") : <p className={ui.hint}>{f.date && formatDateLabel(f.date)}・{t("form.dateHint")}</p>}
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
        <p className={ui.hint}>{t("form.timeHint")}</p>
      </section>

      <section className={ui.card}>
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
          <p className={ui.hint}>{t("form.travelMode")}</p>
        </div>
      </section>

      <section className={ui.card}>
        <fieldset className={s.fieldset} aria-describedby="children-hint">
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
                      {a === 0 ? "未滿 1" : a} {t("form.ageUnit")}
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
                    ×
                  </button>
                )}
              </div>
            ))}
            {f.children.length < 5 && (
              <button type="button" className={ui.soft} onClick={() => set("children", [...f.children, null])}>
                ＋ {t("form.addChild")}
              </button>
            )}
          </div>
          <p className={ui.hint} id="children-hint">
            {t("form.childrenHint")}
          </p>
          {err("children")}
        </fieldset>
      </section>

      <section className={ui.card}>
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
        <p className={ui.hint}>{t("form.mealHint")}</p>
        <hr className={s.hr} />
        <label className={s.switchRow}>
          <span>
            <span className={s.switchTitle}>{t("form.rain")}</span>
            <span className={ui.hint}>{t("form.rainHint")}</span>
          </span>
          <input
            type="checkbox"
            role="switch"
            className={s.switch}
            checked={f.rain_indoor_only}
            onChange={(e) => set("rain_indoor_only", e.target.checked)}
          />
        </label>
      </section>

      <section className={ui.card}>
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
        <fieldset className={s.fieldset} style={{ marginTop: 14 }}>
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
        <p className={ui.hint}>{t("form.prefHint")}</p>
      </section>

      <div className={s.submitBar}>
        <p className={s.privacy}>
          {t("form.privacyNotice")} <Link href="/privacy">{t("form.privacyLink")}</Link>
        </p>
        <button type="submit" className={`${ui.primary} ${ui.large} ${ui.block}`} disabled={busy} aria-busy={busy}>
          {busy && <span className={ui.spinner} aria-hidden="true" />}
          {busy ? t("form.searching") : t("form.submit")}
        </button>
      </div>
    </form>
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
        {QUARTER_TIMES.map((x) => (
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
        <span className={ui.hint} style={{ margin: 0 }}>
          （{t("optional")}）
        </span>
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
