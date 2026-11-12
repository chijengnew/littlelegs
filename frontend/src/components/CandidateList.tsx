"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { Candidate } from "@/lib/api/client";
import { areaOf, ownWarnings, sharedWarnings } from "@/lib/candidates";
import PlaceArt from "./art/PlaceArt";
import { ArrowRightIcon, CheckIcon, PlusIcon, UmbrellaIcon } from "./icons";
import ui from "./ui.module.css";
import s from "./CandidateList.module.css";

export const MAX_PICKS = 5;

type Props = {
  items: Candidate[];
  selected: string[];
  onToggle: (c: Candidate) => void;
  onLimit: () => void;
  rain?: Record<string, number | null>;
  rainLimit?: number;
};

export default function CandidateList({ items, selected, onToggle, onLimit, rain = {}, rainLimit = 60 }: Props) {
  const t = useTranslations();
  const full = selected.length >= MAX_PICKS;
  const shared = sharedWarnings(items);
  return (
    <>
      {shared.length > 0 && (
        <ul className={s.shared} aria-label={t("candidates.sharedNotes")}>
          {shared.map((w) => (
            <li key={w.code}>{w.message}</li>
          ))}
        </ul>
      )}
      <ul className={s.list}>
        {items.map((c) => {
          const order = selected.indexOf(c.place_id) + 1;
          const checked = order > 0;
          const blocked = !checked && full;
          const pick = () => (blocked ? onLimit() : onToggle(c));
          const facilities = Object.entries(c.facilities as Record<string, { status: string }>).filter(
            ([, v]) => v.status === "yes",
          );
          const warnings = ownWarnings(c, shared);
          const area = areaOf(c.address, c.city);
          const pct = rain[c.place_id] ?? null;
          return (
            <li
              key={c.place_id}
              className={s.card}
              data-state={checked ? "picked" : blocked ? "full" : "idle"}
              onClick={(e) => {
                if (!(e.target as HTMLElement).closest("a, button, input, label")) pick();
              }}
            >
              <PlaceArt type={c.primary_type} />
              <div className={s.body}>
                <div className={s.head}>
                  <h3 className={s.name}>{c.name}</h3>
                  <span className={s.distance}>{t("candidates.distance", { km: (c.distance_m / 1000).toFixed(1) })}</span>
                </div>
                {area && <p className={s.area}>{area}</p>}
                <div className={s.chips}>
                  {c.primary_type && <span className={ui.chip}>{t(`types.${c.primary_type}`)}</span>}
                  <IndoorChip value={c.indoor.value} />
                  {pct !== null && (
                    <span className={pct >= rainLimit ? ui.chipAmber : ui.chip}>
                      <UmbrellaIcon size={14} />
                      {t("candidates.rainChance", { p: pct })}
                    </span>
                  )}
                  <span className={ui.chip}>{t("candidates.stay", { m: c.default_stay.minutes })}</span>
                  {facilities.map(([k]) => (
                    <span key={k} className={ui.chipBlue}>
                      {t.has(`facilities.${k}`) ? t(`facilities.${k}`) : k}
                    </span>
                  ))}
                </div>
                {c.reasons.length > 0 && (
                  <ul className={s.reasons} aria-label={t("candidates.reasonsLabel")}>
                    {c.reasons.map((r) => (
                      <li key={r.code} className={ui.chipGreen}>
                        <CheckIcon size={14} />
                        {t.has(`candidates.reasonTags.${r.code}`) ? t(`candidates.reasonTags.${r.code}`) : r.message}
                      </li>
                    ))}
                  </ul>
                )}
                {warnings.length > 0 && (
                  <ul className={s.warnings} aria-label={t("candidates.warningsLabel")}>
                    {warnings.map((w) => (
                      <li key={w.code}>{w.message}</li>
                    ))}
                  </ul>
                )}
                <div className={s.foot}>
                  <Link href={`/places/${c.place_id}?from=candidates`} className={`${ui.navLink} ${s.detailLink}`}>
                    {t("candidates.details")}
                    <ArrowRightIcon className={ui.arrowEnd} />
                  </Link>
                  <label className={s.pick}>
                    <input
                      type="checkbox"
                      className={s.pickInput}
                      checked={checked}
                      aria-disabled={blocked || undefined}
                      onChange={pick}
                      aria-label={t("candidates.select", { name: c.name })}
                    />
                    {checked ? <CheckIcon size={16} /> : blocked ? null : <PlusIcon size={16} />}
                    <span aria-hidden="true">
                      {checked ? t("candidates.picked", { n: order }) : blocked ? t("candidates.pickFull") : t("candidates.pick")}
                    </span>
                  </label>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </>
  );
}

export function IndoorChip({ value }: { value: string | null }) {
  const t = useTranslations("indoor");
  return <span className={ui.chip}>{t(value ?? "unknown")}</span>;
}
