"use client";

import { useTranslations } from "next-intl";
import type { FormState } from "@/lib/form";
import { formatMonthDay } from "@/lib/time";
import { CalendarIcon, ClockIcon, MapPinIcon, UserIcon } from "./icons";
import s from "./Planner.module.css";

export default function TripChips({ form }: { form: FormState }) {
  const t = useTranslations();
  if (!form.start) return null;
  const start = form.start.display;
  const end = form.endSame ? null : (form.end?.display ?? null);
  const ages = form.children.filter((x): x is number => x !== null);
  return (
    <ul className={s.tripChips} aria-label={t("candidates.tripLabel")}>
      <li className={s.tripChip}>
        <CalendarIcon size={16} />
        {formatMonthDay(form.date)}
      </li>
      <li className={s.tripChip}>
        <ClockIcon size={16} />
        {form.depart_time}–{form.return_time}
      </li>
      <li className={s.tripChip}>
        <MapPinIcon size={16} />
        {end ? t("planner.route", { start, end }) : t("planner.roundTrip", { start })}
      </li>
      {ages.length > 0 && (
        <li className={s.tripChip}>
          <UserIcon size={16} />
          {t("planner.ages", { ages: ages.join("、") })}
        </li>
      )}
    </ul>
  );
}
