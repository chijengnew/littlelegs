"use client";

import { useTranslations } from "next-intl";
import type { Schemas } from "@/lib/api/client";
import { tripMax } from "@/lib/weather";
import ui from "./ui.module.css";
import s from "./SidePanels.module.css";

type WeatherProps = { weather: Schemas["WeatherOut"] | null; date: string; depart: string; arrive: string };

export function WeatherCard({ weather, date, depart, arrive }: WeatherProps) {
  const t = useTranslations("weather");
  if (!weather) return null;
  const limit = weather.threshold_percent;
  const filter = weather.rain_filter;
  const rows = (weather.areas ?? []).map((a, i) => ({
    key: i,
    name: a.label ?? t(a.roles.includes("start") ? "nearStart" : a.roles.includes("end") ? "nearEnd" : "otherArea"),
    roles: a.roles,
    percent: tripMax(a, date, depart, arrive),
    indoor: filter && a.status === "triggered",
  }));
  const anyIndoor = rows.some((r) => r.indoor);
  const status = !filter
    ? null
    : anyIndoor
      ? t("triggeredAreas", { t: limit })
      : weather.status === "unverified"
        ? t("unverified")
        : null;
  if (!rows.length && !status) return null;
  return (
    <section
      className={`${ui.card} ${s.weather}`}
      aria-labelledby="weather-title"
      data-status={anyIndoor ? "triggered" : filter && weather.status === "unverified" ? "unverified" : "ok"}
    >
      <h2 className={s.weatherTitle} id="weather-title">
        {t("routeTitle")}
      </h2>
      {status && <p className={s.weatherStatus}>{status}</p>}
      {rows.length > 0 && (
        <ul className={s.meters}>
          {rows.map((r) => (
            <li key={r.key} className={s.meterRow}>
              <span className={s.meterName}>
                {r.name}
                {r.roles.map((role) => (
                  <span key={role} className={s.role}>
                    {t(`roles.${role}`)}
                  </span>
                ))}
                {r.indoor && <span className={s.indoorOnly}>{t("indoorOnly")}</span>}
              </span>
              <span className={s.meterValue}>{r.percent === null ? t("noData") : `${r.percent}%`}</span>
              <span className={s.track} aria-hidden="true">
                {r.percent !== null && <span className={s.fill} data-high={r.percent >= limit || undefined} style={{ width: `${r.percent}%` }} />}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function LodgingList({ lodging }: { lodging: Schemas["LodgingOut"] }) {
  const t = useTranslations();
  const facility = (f: string) => (t.has(`facilities.${f}`) ? t(`facilities.${f}`) : f);
  return (
    <section className={`${ui.card} ${s.lodgingCard}`} aria-labelledby="lodging-title">
      <h2 className={s.lodgingTitle} id="lodging-title">
        {t("lodging.title")}
      </h2>
      {lodging.items.length === 0 ? (
        <p className={s.small}>{lodging.note ?? t("lodging.empty")}</p>
      ) : (
        <>
          <p className={s.small}>{t("lodging.hint")}</p>
          <ul className={s.lodging} tabIndex={0} aria-labelledby="lodging-title">
            {lodging.items.map((h) => (
              <li key={h.place_id}>
                <div className={s.lodgingHead}>
                  <strong>{h.name}</strong>
                  <span className={s.small}>{t("candidates.distance", { km: (h.distance_m / 1000).toFixed(1) })}</span>
                </div>
                <p className={h.family_facilities.length ? s.lodgingFacilities : s.small}>
                  {h.family_facilities.length ? h.family_facilities.map(facility).join("、") : t("lodging.unknown")}
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
