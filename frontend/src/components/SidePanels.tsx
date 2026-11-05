"use client";

import { useTranslations } from "next-intl";
import type { Schemas } from "@/lib/api/client";
import ui from "./ui.module.css";
import s from "./SidePanels.module.css";

export function WeatherNotice({ weather }: { weather: Schemas["WeatherOut"] | null }) {
  const t = useTranslations("weather");
  if (!weather || weather.status === "not_requested") return null;
  const p = weather.max_precipitation_percent ?? "—";
  const tt = weather.threshold_percent;
  const cls =
    weather.status === "triggered" ? ui.bannerInfo : weather.status === "unverified" ? ui.bannerWarn : ui.bannerOk;
  return (
    <div className={cls} role="status">
      <span aria-hidden="true">☂</span>
      <div>
        <strong>{t("title")}</strong>
        <div>
          {weather.status === "unverified" ? t("unverified") : t(weather.status, { p, t: tt })}
        </div>
        {weather.uncovered.length > 0 && <div>{t("uncovered", { parts: weather.uncovered.join("、") })}</div>}
        {weather.explanation && <div className={s.small}>{weather.explanation}</div>}
      </div>
    </div>
  );
}

export function LodgingList({ lodging }: { lodging: Schemas["LodgingOut"] }) {
  const t = useTranslations();
  return (
    <section className={ui.card} aria-labelledby="lodging-title">
      <h2 className={ui.cardTitle} id="lodging-title">
        {t("lodging.title")}
      </h2>
      <p className={ui.hint} style={{ marginTop: -6, marginBottom: 10 }}>
        {t("lodging.hint")}
      </p>
      {lodging.items.length === 0 ? (
        <p className={ui.hint}>{lodging.note ?? t("lodging.empty")}</p>
      ) : (
        <ul className={s.lodging}>
          {lodging.items.map((h) => (
            <li key={h.place_id}>
              <div className={s.lodgingHead}>
                <strong>{h.name}</strong>
                <span className={s.small}>{(h.distance_m / 1000).toFixed(1)} km</span>
              </div>
              <div className={s.chips}>
                <span className={h.label === "有親子設施資訊" ? ui.chipGreen : ui.chip}>{h.label}</span>
                {h.family_facilities.map((f) => (
                  <span key={f} className={ui.chipBlue}>
                    {t.has(`facilities.${f}`) ? t(`facilities.${f}`) : f}
                  </span>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function LockedMap({ variant, message }: { variant: "locked" | "stale" | "pending"; message?: string | null }) {
  const t = useTranslations("map");
  const title = variant === "locked" ? message || t("lockedTitle") : t(`${variant}Title`);
  return (
    <section className={s.map} aria-label={title}>
      <svg viewBox="0 0 320 180" className={s.mapArt} aria-hidden="true">
        <rect width="320" height="180" fill="#e7f3ff" />
        <path d="M0 120 C60 100 90 150 160 130 S260 90 320 110 V180 H0Z" fill="#d4e7fd" />
        <path d="M40 0 V180 M120 0 V180 M200 0 V180 M280 0 V180 M0 45 H320 M0 90 H320" stroke="#c4dcf7" strokeWidth="6" />
        <circle cx="160" cy="80" r="34" fill="#fff" />
        <rect x="146" y="78" width="28" height="22" rx="4" fill="#1877f2" />
        <path d="M151 78 V71 a9 9 0 0 1 18 0 V78" stroke="#1877f2" strokeWidth="4" fill="none" />
      </svg>
      <div className={s.mapText}>
        <strong>{title}</strong>
        <span>{t(`${variant}Body`)}</span>
      </div>
    </section>
  );
}
