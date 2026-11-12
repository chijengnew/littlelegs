"use client";

import { useEffect, useState, type MouseEvent } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { api, type Schemas } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import { displayAddress, facilityNote, typeNote } from "@/lib/placeText";
import PlaceArt from "./art/PlaceArt";
import { IndoorChip } from "./CandidateList";
import StampCard from "./explore/StampCard";
import { SkeletonCard } from "./Skeleton";
import StatePanel from "./StatePanel";
import { ArrowLeftIcon, ArrowRightIcon } from "./icons";
import ui from "./ui.module.css";
import s from "./PlaceDetail.module.css";
import { useAuth } from "./AuthProvider";
import { currentFirebaseUid } from "@/lib/firebaseClient";

type Detail = Schemas["PlaceDetailResponse"];

type HistoryEntries = { currentEntry: { index: number } | null; entries(): { url: string | null }[] };

const CONF_CHIP: Record<string, string> = {
  confirmed: ui.chipGreen,
  inferred: ui.chipAmber,
  estimated: ui.chipAmber,
};

const BACK: Record<string, { href: string; from: (path: string) => boolean }> = {
  candidates: { href: "/planner", from: (p) => p === "/planner" },
  plan: { href: "/planner", from: (p) => p === "/planner" },
  history: { href: "/account?tab=history", from: (p) => p.startsWith("/account/histories/") },
  favorites: { href: "/account?tab=favorites", from: (p) => p.startsWith("/account/favorites/") },
  passport: { href: "/explore/passport", from: (p) => p === "/explore/passport" },
};

function previousPath(): string | null {
  const nav = (window as Window & { navigation?: HistoryEntries }).navigation;
  const index = nav?.currentEntry?.index ?? 0;
  if (!nav || index < 1) return null;
  const url = nav.entries()[index - 1]?.url;
  if (!url) return null;
  const prev = new URL(url);
  return prev.origin === window.location.origin ? prev.pathname : null;
}

export default function PlaceDetail() {
  const t = useTranslations();
  const router = useRouter();
  const from = useSearchParams().get("from") ?? "";
  const fromList = from === "candidates";
  const backTo = Object.hasOwn(BACK, from) ? BACK[from] : undefined;
  const { user, ready } = useAuth();
  const uid = user?.uid ?? null;
  const { id } = useParams<{ id: string }>();
  const [result, setResult] = useState<{ data: Detail; owner: string | null } | null>(null);
  const data = ready && result?.owner === uid ? result.data : null;
  const [err, setErr] = useState<{ notFound: boolean; message: string } | null>(null);

  useEffect(() => {
    if (!ready || currentFirebaseUid() !== uid) return;
    let alive = true;
    api
      .GET("/v1/places/{place_id}", { params: { path: { place_id: id } } })
      .then(({ data, error, response }) => {
        if (!alive) return;
        if (data) { setResult({ data, owner: uid }); setErr(null); }
        else setErr(response.status === 404 ? { notFound: true, message: "" } : { notFound: false, message: toUiError(t, error, response.status).message });
      })
      .catch((e) => alive && setErr({ notFound: false, message: toUiError(t, e).message }));
    return () => {
      alive = false;
    };
  }, [id, t, uid, ready]);

  function back(event: MouseEvent<HTMLAnchorElement>) {
    const prev = backTo ? previousPath() : null;
    if (!backTo || prev === null || !backTo.from(prev)) return;
    event.preventDefault();
    router.back();
  }

  const conf = (c: string) => <span className={CONF_CHIP[c] ?? ui.chip}>{t(`place.confirmation.${c}`)}</span>;
  const address = data ? displayAddress(data.place.address) ?? data.place.city : null;

  return (
    <div className={s.wrap}>
      <Link href={backTo?.href ?? "/planner"} className={`${ui.navLink} ${s.back}`} onClick={back}>
        <ArrowLeftIcon className={ui.arrowStart} />
        {fromList ? t("place.backToCandidates") : t("place.back")}
      </Link>
      {!data && !err && (
        <>
          <p className="visually-hidden" role="status">
            {t("place.loading")}
          </p>
          <SkeletonCard lines={3} />
          <SkeletonCard lines={5} />
        </>
      )}
      {err && (
        <StatePanel
          tone={err.notFound ? "notFound" : "error"}
          inline
          live={err.notFound ? "status" : "alert"}
          title={err.notFound ? t("place.notFound") : t("place.loadFailed")}
          description={<p>{err.notFound ? t("place.notFoundBody") : err.message}</p>}
          actions={
            <>
              <Link className={ui.primary} href="/planner">{t("place.toPlanner")}</Link>
              <Link className={ui.secondary} href="/">{t("state.home")}</Link>
            </>
          }
        />
      )}
      {data && (
        <>
          <header className={`${ui.card} ${s.hero}`}>
            <div className={s.heroHead}>
              <PlaceArt type={data.place.primary_type} className={s.heroIcon} />
              <div className={s.heroTitle}>
                <h1 className={s.name}>{data.place.name}</h1>
                {address && <p className={s.address}>{address}</p>}
              </div>
            </div>
            <div className={s.chips}>
              {data.place.primary_type && <span className={ui.chipBlue}>{t(`types.${data.place.primary_type}`)}</span>}
              {data.place.age_range && (
                <span className={ui.chip}>
                  {t("candidates.ageRange", { min: data.place.age_range.min_age, max: data.place.age_range.max_age })}
                </span>
              )}
              <IndoorChip value={data.place.indoor.value} />
              {data.evidence.facilities
                .filter((x) => x.status === "yes")
                .map((x) => (
                  <span key={x.facility} className={ui.chipGreen}>
                    {t.has(`facilities.${x.facility}`) ? t(`facilities.${x.facility}`) : x.facility}
                  </span>
                ))}
              {data.place.source_stay_minutes && (
                <span className={ui.chip}>
                  {t("place.sourceStayValue", { m: data.place.source_stay_minutes })}
                </span>
              )}
            </div>
            {data.place.removed && (
              <div className={ui.bannerWarn}>{data.place.removed_note ?? t("place.removed")}</div>
            )}
          </header>

          {data.place.kind === "attraction" && (
            <StampCard placeId={data.place.place_id} type={data.place.primary_type} removed={data.place.removed} />
          )}

          <section className={s.section} aria-labelledby="place-evidence">
            <h2 className={s.sectionTitle} id="place-evidence">{t("place.evidence")}</h2>
            <div className={s.facts}>
              <article className={`${ui.card} ${s.fact}`} aria-labelledby="fact-age">
                <h3 className={s.factTitle} id="fact-age">{t("place.age")}</h3>
                {data.evidence.age_ranges.length === 0 ? (
                  <p className={s.none}>
                    {data.place.age_range
                      ? t("place.ageEstimated", { min: data.place.age_range.min_age, max: data.place.age_range.max_age })
                      : t("place.ageNone")}
                  </p>
                ) : (
                  <ul className={s.factList}>
                    {data.evidence.age_ranges.map((x, i) => (
                      <li key={i}>
                        <span className={s.factValue}>{t("place.ageRange", { min: x.min_age, max: x.max_age })}</span>
                        {conf(x.confirmation)}
                      </li>
                    ))}
                  </ul>
                )}
              </article>
              <article className={`${ui.card} ${s.fact}`} aria-labelledby="fact-facilities">
                <h3 className={s.factTitle} id="fact-facilities">{t("place.facilities")}</h3>
                {data.evidence.facilities.length === 0 ? (
                  <p className={s.none}>{t("place.noData")}</p>
                ) : (
                  <ul className={s.factList}>
                    {data.evidence.facilities.map((x, i) => {
                      const note = facilityNote(x.evidence);
                      return (
                        <li key={i}>
                          <span className={s.factValue}>
                            {t.has(`facilities.${x.facility}`) ? t(`facilities.${x.facility}`) : x.facility}：{t(`place.status.${x.status}`)}
                          </span>
                          {conf(x.confirmation)}
                          {note && <span className={s.ev}>{note}</span>}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </article>
              <article className={`${ui.card} ${s.fact}`} aria-labelledby="fact-indoor">
                <h3 className={s.factTitle} id="fact-indoor">{t("place.indoor")}</h3>
                {data.evidence.indoor ? (
                  <ul className={s.factList}>
                    <li>
                      <span className={s.factValue}>
                        {data.evidence.indoor.value ? t(`indoor.${data.evidence.indoor.value}`) : t("indoor.unknown")}
                      </span>
                      {conf(data.evidence.indoor.confirmation)}
                    </li>
                  </ul>
                ) : (
                  <p className={s.none}>{t("indoor.unknown")}</p>
                )}
              </article>
              <article className={`${ui.card} ${s.fact}`} aria-labelledby="fact-type">
                <h3 className={s.factTitle} id="fact-type">{t("place.type")}</h3>
                {data.evidence.types.length === 0 ? (
                  <p className={s.none}>{t("place.noData")}</p>
                ) : (
                  <ul className={s.factList}>
                    {data.evidence.types.map((x, i) => {
                      const note = typeNote(x.evidence);
                      return (
                        <li key={i}>
                          <span className={s.factValue}>{t(`types.${x.type}`)}</span>
                          {conf(x.confirmation)}
                          {note && <span className={s.ev}>{note}</span>}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </article>
            </div>
            <p className={s.report}>
              <Link className={ui.navLink} href={`/feedback?from=place_detail&type=place_data&place=${data.place.place_id}`}>
                {t("feedback.reportPlace")}
                <ArrowRightIcon className={ui.arrowEnd} />
              </Link>
            </p>
          </section>
        </>
      )}
    </div>
  );
}
