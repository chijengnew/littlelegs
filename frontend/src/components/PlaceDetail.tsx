"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { api, type Schemas } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import { IndoorChip } from "./CandidateList";
import ui from "./ui.module.css";
import s from "./PlaceDetail.module.css";
import { useAuth } from "./AuthProvider";
import { currentFirebaseUid } from "@/lib/firebaseClient";

type Detail = Schemas["PlaceDetailResponse"];

export default function PlaceDetail() {
  const t = useTranslations();
  const { user, ready } = useAuth();
  const uid = user?.uid ?? null;
  const { id } = useParams<{ id: string }>();
  const [result, setResult] = useState<{ data: Detail; owner: string | null } | null>(null);
  const data = ready && result?.owner === uid ? result.data : null;
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!ready || currentFirebaseUid() !== uid) return;
    let alive = true;
    api
      .GET("/v1/places/{place_id}", { params: { path: { place_id: id } } })
      .then(({ data, error, response }) => {
        if (!alive) return;
        if (data) { setResult({ data, owner: uid }); setErr(null); }
        else setErr(response.status === 404 ? t("place.notFound") : toUiError(t, error, response.status).message);
      })
      .catch((e) => alive && setErr(toUiError(t, e).message));
    return () => {
      alive = false;
    };
  }, [id, t, uid, ready]);

  const conf = (c: string) => t(`place.confirmation.${c}`);

  return (
    <div className={s.wrap}>
      <Link href="/" className={ui.ghost}>
        ← {t("place.back")}
      </Link>
      {!data && !err && (
        <p className={ui.hint} role="status">
          {t("place.loading")}
        </p>
      )}
      {err && (
        <div className={ui.bannerError} role="alert">
          {err}
        </div>
      )}
      {data && (
        <>
          <section className={ui.card}>
            <h1 className={s.name}>{data.place.name}</h1>
            <p className={ui.hint} style={{ margin: "0 0 4px" }}>
              <Link href={`/feedback?from=place_detail&type=place_data&place=${data.place.place_id}`}>
                {t("feedback.reportPlace")}
              </Link>
            </p>
            <p className={s.address}>{data.place.address ?? data.place.city}</p>
            {data.place.removed && (
              <div className={ui.bannerWarn}>{data.place.removed_note ?? t("place.removed")}</div>
            )}
            <div className={s.chips}>
              {data.place.primary_type && <span className={ui.chipBlue}>{t(`types.${data.place.primary_type}`)}</span>}
              <IndoorChip value={data.place.indoor.value} confirmation={data.place.indoor.confirmation} />
              {data.place.source_stay_minutes && (
                <span className={ui.chip}>
                  {t("place.sourceStay")} {data.place.source_stay_minutes} 分鐘
                </span>
              )}
            </div>
          </section>

          <section className={ui.card}>
            <h2 className={ui.cardTitle}>{t("place.evidence")}</h2>
            <dl className={s.dl}>
              <dt>{t("place.type")}</dt>
              <dd>
                {data.evidence.types.length === 0
                  ? "—"
                  : data.evidence.types.map((x, i) => (
                      <div key={i}>
                        {t(`types.${x.type}`)}（{conf(x.confirmation)}）
                        {x.evidence && <span className={s.ev}>{x.evidence}</span>}
                      </div>
                    ))}
              </dd>
              <dt>{t("place.indoor")}</dt>
              <dd>
                {data.evidence.indoor ? (
                  <>
                    {data.evidence.indoor.value ? t(`indoor.${data.evidence.indoor.value}`) : t("indoor.unknown")}（
                    {conf(data.evidence.indoor.confirmation)}）
                    {data.evidence.indoor.evidence && <span className={s.ev}>{data.evidence.indoor.evidence}</span>}
                  </>
                ) : (
                  t("indoor.unknown")
                )}
              </dd>
              <dt>{t("place.facilities")}</dt>
              <dd>
                {data.evidence.facilities.length === 0
                  ? "—"
                  : data.evidence.facilities.map((x, i) => (
                      <div key={i}>
                        {t.has(`facilities.${x.facility}`) ? t(`facilities.${x.facility}`) : x.facility}：{t(`place.status.${x.status}`)}（{conf(x.confirmation)}）
                        {x.evidence && <span className={s.ev}>{x.evidence}</span>}
                      </div>
                    ))}
              </dd>
              <dt>{t("place.age")}</dt>
              <dd>
                {data.evidence.age_ranges.length === 0
                  ? data.place.age_range
                    ? t("place.ageEstimated", { min: data.place.age_range.min_age, max: data.place.age_range.max_age })
                    : t("place.ageNone")
                  : data.evidence.age_ranges.map((x, i) => (
                      <div key={i}>
                        {x.min_age}–{x.max_age} 歲（{conf(x.confirmation)}）
                      </div>
                    ))}
              </dd>
            </dl>
          </section>

          <section className={ui.card}>
            <h2 className={ui.cardTitle}>{t("place.sources")}</h2>
            <ul className={s.sources}>
              {data.sources.map((src) => (
                <li key={src.source_record_id}>
                  <a href={src.source_url} target="_blank" rel="noreferrer" className={s.srcTitle}>
                    {src.dataset_title} ↗
                  </a>
                  {src.provider && <div className={ui.hint}>{src.provider}</div>}
                  <div className={s.srcMeta}>
                    <span>
                      {t("place.license")}：{src.license}
                    </span>
                    {src.dataset_updated_at && (
                      <span>
                        {t("place.datasetUpdated")}：{src.dataset_updated_at}
                      </span>
                    )}
                    {src.record_updated_at && (
                      <span>
                        {t("place.recordUpdated")}：{src.record_updated_at}
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
