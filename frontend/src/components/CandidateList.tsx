"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { Candidate } from "@/lib/api/client";
import ui from "./ui.module.css";
import s from "./CandidateList.module.css";

type Props = {
  items: Candidate[];
  selected: string[];
  onToggle: (c: Candidate) => void;
};

export default function CandidateList({ items, selected, onToggle }: Props) {
  const t = useTranslations();
  const full = selected.length >= 5;
  return (
    <ol className={s.list}>
      {items.map((c, i) => {
        const checked = selected.includes(c.place_id);
        const disabled = !checked && full;
        const facilities = Object.entries(c.facilities as Record<string, { status: string }>).filter(
          ([, v]) => v.status === "yes",
        );
        return (
          <li key={c.place_id} className={checked ? s.itemChecked : s.item}>
            <label className={s.pick} aria-disabled={disabled}>
              <input
                type="checkbox"
                className={s.checkbox}
                checked={checked}
                disabled={disabled}
                onChange={() => onToggle(c)}
                aria-label={t("candidates.select", { name: c.name })}
              />
              <span className={s.rank} aria-hidden="true">
                {i + 1}
              </span>
            </label>
            <div className={s.body}>
              <div className={s.head}>
                <h3 className={s.name}>{c.name}</h3>
                <span className={s.distance}>
                  {(c.distance_m / 1000).toFixed(1)} km
                  <span className="visually-hidden">（{c.distance_note}）</span>
                </span>
              </div>
              <p className={s.address}>{c.address ?? c.city}</p>
              <div className={s.chips}>
                {c.primary_type && <span className={ui.chipBlue}>{t(`types.${c.primary_type}`)}</span>}
                <IndoorChip value={c.indoor.value} confirmation={c.indoor.confirmation} />
                {c.age === "all_ok" && <span className={ui.chipGreen}>✓ {t("candidates.ageOk")}</span>}
                {c.age_range && (
                  <span className={ui.chip}>{t("candidates.ageRange", { min: c.age_range.min_age, max: c.age_range.max_age })}</span>
                )}
                {facilities.map(([k]) => (
                  <span key={k} className={ui.chipGreen}>
                    {t.has(`facilities.${k}`) ? t(`facilities.${k}`) : k}
                  </span>
                ))}
                <span className={ui.chip}>{t("candidates.stay", { m: c.default_stay.minutes })}</span>
              </div>
              {c.reasons.length > 0 && (
                <ul className={s.reasons}>
                  {c.reasons.map((r) => (
                    <li key={r.code}>{r.message}</li>
                  ))}
                </ul>
              )}
              <div className={s.foot}>
                <Link href={`/places/${c.place_id}`} target="_blank" className={s.detailLink}>
                  {t("candidates.details")} ↗
                </Link>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function IndoorChip({ value, confirmation }: { value: string | null; confirmation: string }) {
  const t = useTranslations("indoor");
  if (!value) return <span className={ui.chip}>{t("unknown")}</span>;
  return (
    <span className={ui.chip}>
      {t(value)}
      {confirmation === "inferred" && `（${t("inferred")}）`}
    </span>
  );
}
