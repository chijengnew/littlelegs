"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api, type Schemas } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import StatePanel from "../StatePanel";
import { SkeletonList } from "../Skeleton";
import { Badge } from "./ExploreArt";
import ui from "../ui.module.css";
import s from "./explore.module.css";

type MissionList = Schemas["MissionList"];
type Mission = Schemas["MissionOut"];

export default function Missions() {
  const t = useTranslations();
  const [data, setData] = useState<MissionList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let alive = true;
    api
      .GET("/v1/missions")
      .then(({ data, error, response }) => {
        if (!alive) return;
        if (data) {
          setData(data);
          setError(null);
        } else setError(toUiError(t, error, response.status).message);
      })
      .catch((e) => alive && setError(toUiError(t, e).message));
    return () => {
      alive = false;
    };
  }, [t, attempt]);

  if (!data) {
    if (!error) return <div aria-busy="true"><SkeletonList count={2} lines={2} /></div>;
    return (
      <StatePanel
        tone="error"
        inline
        live="alert"
        title={t("explore.missions.loadFailed")}
        description={<p>{error}</p>}
        actions={<button type="button" className={ui.primary} onClick={() => setAttempt((n) => n + 1)}>{t("saved.retry")}</button>}
      />
    );
  }

  const unlocked = data.items.filter((m) => m.unlocked).length;
  return (
    <>
      <div className={s.summary}>
        <h2>{t("explore.missions.summary", { n: unlocked, total: data.items.length })}</h2>
      </div>
      <ul className={s.missions}>
        {data.items.map((m) => (
          <li key={m.code}>
            <MissionCard mission={m} />
          </li>
        ))}
      </ul>
      <p className={s.note}>{t("explore.missions.note")}</p>
    </>
  );
}

function MissionCard({ mission: m }: { mission: Mission }) {
  const t = useTranslations("explore.missions");
  const known = t.has(`items.${m.code}.title`);
  const title = known ? t(`items.${m.code}.title`) : m.code;
  const done = Math.min(m.progress, m.threshold);
  return (
    <article className={`${ui.card} ${s.mission}`} aria-labelledby={`mission-${m.code}`}>
      <Badge code={m.code} unlocked={m.unlocked} size={80} />
      <div className={s.missionBody}>
        <h3 id={`mission-${m.code}`}>{title}</h3>
        {known && <p>{t(`items.${m.code}.description`)}</p>}
        <div className={s.progress}>
          <div
            className={s.bar}
            data-done={m.unlocked ? "" : undefined}
            role="progressbar"
            aria-label={t("progressLabel", { title })}
            aria-valuemin={0}
            aria-valuemax={m.threshold}
            aria-valuenow={done}
          >
            <div className={s.barFill} style={{ width: `${(done / m.threshold) * 100}%` }} />
          </div>
          <span className={s.count}>{t("progress", { n: done, total: m.threshold })}</span>
        </div>
        <span className={m.unlocked ? ui.chipGreen : ui.chip} style={{ justifySelf: "start" }}>
          {t(m.unlocked ? "unlocked" : "locked")}
        </span>
      </div>
    </article>
  );
}
