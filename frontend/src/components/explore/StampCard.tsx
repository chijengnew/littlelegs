"use client";

import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import { withNext } from "@/lib/authFlow";
import { currentFirebaseUid } from "@/lib/firebaseClient";
import {
  GeoError,
  failureKey,
  geoKey,
  locate,
  manualAllowed,
  newAttempt,
  stampDay,
  uncertain,
  type Attempt,
  type CheckIn,
} from "@/lib/stamping";
import { useAuth } from "../AuthProvider";
import { ArrowRightIcon } from "../icons";
import { CheckInDates } from "./CheckInDates";
import { Stamp, StampIcon } from "./ExploreArt";
import ui from "../ui.module.css";
import s from "./explore.module.css";

type Phase =
  | { name: "idle" }
  | { name: "intro" }
  | { name: "locating" }
  | { name: "sending"; attempt: Attempt }
  | { name: "failed"; message: string; retry: Attempt | null; manual: boolean }
  | { name: "ceremony"; checkIn: CheckIn; upgraded: boolean }
  | { name: "done"; text: string };

type Status = { loading: true } | { error: string } | { checkIn: CheckIn | null };

type Props = { placeId: string; type: string | null | undefined; removed: boolean };

export default function StampCard(props: Props) {
  const t = useTranslations();
  const auth = useAuth();
  if (!auth.configured || !auth.booted || auth.pending || !auth.user) {
    return (
      <section className={`${ui.card} ${s.card}`} aria-labelledby="stamp-title" id="stamp">
        <h2 className={s.cardTitle} id="stamp-title">
          <StampIcon size={22} />
          {t("explore.stamp.title")}
        </h2>
        <p className={s.lead}>{t("explore.stamp.guestLead")}</p>
        <div className={s.actions}>
          {auth.configured && auth.booted && !auth.pending && (
            <Link className={ui.primary} href={withNext("/login", `/places/${props.placeId}`)}>{t("explore.stamp.login")}</Link>
          )}
          <Link className={`${ui.navLink} ${s.howTo}`} href="/explore/passport">
            {t("explore.stamp.howTo")}
            <ArrowRightIcon className={ui.arrowEnd} />
          </Link>
        </div>
        {!auth.configured && <p className={s.muted}>{t("auth.disabledFeature")}</p>}
      </section>
    );
  }
  if (!auth.member) return null;
  return <MemberStamp key={`${auth.user.uid}:${props.placeId}`} {...props} uid={auth.user.uid} />;
}

function MemberStamp({ placeId, type, removed, uid }: Props & { uid: string }) {
  const t = useTranslations();
  const [status, setStatus] = useState<Status>({ loading: true });
  const [phase, setPhase] = useState<Phase>({ name: "idle" });
  const [reload, setReload] = useState(0);
  const busy = useRef(false);
  const gen = useRef(0);
  const live = useRef<HTMLParagraphElement>(null);

  function reset() {
    gen.current += 1;
    busy.current = false;
    setPhase({ name: "idle" });
  }

  useLayoutEffect(() => () => reset(), []);

  useEffect(() => {
    if (currentFirebaseUid() !== uid) return;
    let alive = true;
    api
      .GET("/v1/check-ins", { params: { query: { place_id: placeId, limit: 1 } } })
      .then(({ data, error, response }) => {
        if (!alive) return;
        if (data) setStatus({ checkIn: data.items[0] ?? null });
        else setStatus({ error: toUiError(t, error, response.status).message });
      })
      .catch((e) => alive && setStatus({ error: toUiError(t, e).message }));
    return () => {
      alive = false;
    };
  }, [placeId, uid, t, reload]);

  useEffect(() => {
    if (phase.name === "ceremony" || phase.name === "failed") live.current?.focus();
  }, [phase.name]);

  async function send(attempt: Attempt, run: number = ++gen.current) {
    busy.current = true;
    setPhase({ name: "sending", attempt });
    try {
      const { data, error, response } = await api.POST("/v1/check-ins", {
        params: { header: { "Idempotency-Key": attempt.key } },
        body: attempt.body,
      });
      if (gen.current !== run) return;
      if (data) {
        setStatus({ checkIn: data.check_in });
        if (data.check_in.verification_method === "location" && data.outcome !== "existing") {
          setPhase({ name: "ceremony", checkIn: data.check_in, upgraded: data.outcome === "upgraded" });
        } else {
          setPhase({ name: "done", text: t(data.check_in.verification_method === "manual" ? "explore.stamp.manualSaved" : "explore.stamp.stamped") });
        }
        return;
      }
      const err = toUiError(t, error, response.status);
      fail(err.code, err.message, uncertain(err) ? attempt : null);
    } catch (e) {
      if (gen.current !== run) return;
      const err = toUiError(t, e);
      fail(err.code, err.message, uncertain(err) ? attempt : null);
    } finally {
      if (gen.current === run) busy.current = false;
    }
  }

  function fail(code: string, fallback: string, retry: Attempt | null) {
    const key = failureKey(retry && code !== "NETWORK" ? "NETWORK" : code);
    setPhase({ name: "failed", message: key ? t(key) : fallback, retry, manual: manualAllowed(code) });
  }

  async function startLocate() {
    if (busy.current) return;
    busy.current = true;
    const run = ++gen.current;
    setPhase({ name: "locating" });
    let fix;
    try {
      fix = await locate();
    } catch (e) {
      if (gen.current !== run) return;
      busy.current = false;
      const reason = e instanceof GeoError ? e.reason : "unavailable";
      setPhase({ name: "failed", message: t(geoKey(reason)), retry: null, manual: true });
      return;
    }
    if (gen.current !== run) return;
    await send(newAttempt(placeId, fix), run);
  }

  function recordManually() {
    if (busy.current) return;
    void send(newAttempt(placeId, null));
  }

  if ("loading" in status) {
    return (
      <section className={`${ui.card} ${s.card}`} aria-labelledby="stamp-title" aria-busy="true" id="stamp">
        <h2 className={s.cardTitle} id="stamp-title"><StampIcon size={22} />{t("explore.stamp.title")}</h2>
        <p className={s.muted}>{t("place.loading")}</p>
      </section>
    );
  }

  const current = "checkIn" in status ? status.checkIn : null;
  const working = phase.name === "locating" || phase.name === "sending";

  return (
    <section className={`${ui.card} ${s.card}`} aria-labelledby="stamp-title" id="stamp">
      <div className={s.cardHead}>
        <h2 className={s.cardTitle} id="stamp-title"><StampIcon size={22} />{t("explore.stamp.title")}</h2>
        <Link className={`${ui.navLink} ${s.howTo}`} href="/explore/passport">
          {t("explore.stamp.toPassport")}
          <ArrowRightIcon className={ui.arrowEnd} />
        </Link>
      </div>

      {"error" in status && (
        <div className={ui.bannerError} role="alert">
          <div>
            <p className={s.lead}>{t("explore.stamp.loadFailed")} {status.error}</p>
            <button type="button" className={ui.inlineNav} style={{ marginLeft: "calc(var(--space-2) * -1)" }} onClick={() => setReload((n) => n + 1)}>
              {t("saved.retry")}
            </button>
          </div>
        </div>
      )}

      {phase.name === "ceremony" ? (
        <Ceremony checkIn={phase.checkIn} upgraded={phase.upgraded} type={type} live={live} />
      ) : (
        current && (
          <div className={s.status}>
            <Stamp type={type} method={current.verification_method} label={stampDay(current).replaceAll("-", ".")} size={96} />
            <div className={s.statusText}>
              <p className={current.verification_method === "location" ? ui.chipGreen : ui.chip} style={{ justifySelf: "start" }}>
                {t(current.verification_method === "location" ? "explore.stamp.location" : "explore.stamp.manual")}
              </p>
              <CheckInDates checkIn={current} />
              {current.verification_method === "manual" && <p className={s.muted}>{t("explore.stamp.manualLead")}</p>}
            </div>
          </div>
        )
      )}

      {phase.name === "done" && (
        <p className={ui.bannerOk} role="status">{phase.text}</p>
      )}

      {phase.name !== "ceremony" && !current && !("error" in status) && (
        <p className={s.lead}>{removed ? t("explore.stamp.removed") : t("explore.stamp.none")}</p>
      )}
      {current && removed && <p className={s.muted}>{t("explore.stamp.removed")}</p>}

      {!removed && current?.verification_method !== "location" && (phase.name === "idle" || phase.name === "done") && !("error" in status) && (
        <div className={s.actions}>
          <button type="button" className={ui.primary} onClick={() => setPhase({ name: "intro" })}>
            <StampIcon />
            {current ? t("explore.stamp.upgrade") : t("explore.stamp.start")}
          </button>
        </div>
      )}

      {(phase.name === "intro" || working) && (
        <div className={s.panel} role="group" aria-labelledby="stamp-intro">
          <h3 id="stamp-intro">{t("explore.stamp.introTitle")}</h3>
          <p>{t("explore.stamp.intro")}</p>
          <p className={s.muted}>{t("explore.stamp.limits")}</p>
          <div className={s.actions}>
            <button type="button" className={ui.secondary} onClick={reset} disabled={phase.name === "sending"}>
              {t("explore.stamp.cancel")}
            </button>
            <button type="button" className={ui.primary} onClick={startLocate} disabled={working} aria-busy={working}>
              {phase.name === "locating" ? t("explore.stamp.locating") : phase.name === "sending" ? t("explore.stamp.checking") : t("explore.stamp.locate")}
            </button>
          </div>
          <p className="visually-hidden" role="status">
            {phase.name === "locating" ? t("explore.stamp.locating") : phase.name === "sending" ? t("explore.stamp.checking") : ""}
          </p>
        </div>
      )}

      {phase.name === "failed" && (
        <div className={s.panel}>
          <p className={ui.bannerWarn} role="alert" tabIndex={-1} ref={live}>{phase.message}</p>
          <div className={s.actions}>
            {phase.retry && (
              <button type="button" className={ui.primary} onClick={() => phase.retry && send(phase.retry)}>
                {t("explore.stamp.resend")}
              </button>
            )}
            {phase.manual && (
              <button type="button" className={phase.retry ? ui.secondary : ui.primary} onClick={startLocate}>
                {t("explore.stamp.relocate")}
              </button>
            )}
            {phase.manual && !current && (
              <button type="button" className={ui.secondary} onClick={recordManually}>
                {t("explore.stamp.manualRecord")}
              </button>
            )}
            <button type="button" className={ui.navLink} onClick={reset}>
              {t("explore.stamp.cancel")}
            </button>
          </div>
          {phase.manual && !current && <p className={s.muted}>{t("explore.stamp.manualNote")}</p>}
        </div>
      )}
    </section>
  );
}

function Ceremony({
  checkIn,
  upgraded,
  type,
  live,
}: {
  checkIn: CheckIn;
  upgraded: boolean;
  type: string | null | undefined;
  live: RefObject<HTMLParagraphElement | null>;
}) {
  const t = useTranslations();
  const [pressed, setPressed] = useState(false);
  useEffect(() => {
    if (pressed) live.current?.focus();
  }, [pressed, live]);
  return (
    <div className={s.ceremony}>
      <h3>{t(upgraded ? "explore.stamp.upgradedTitle" : "explore.stamp.successTitle")}</h3>
      <p tabIndex={-1} ref={live} role="status">{pressed ? t("explore.stamp.stamped") : t("explore.stamp.tapHint")}</p>
      {pressed ? (
        <span className={s.stampSlot}>
          <Stamp type={type} method="location" label={stampDay(checkIn).replaceAll("-", ".")} size={128} className={s.press} />
        </span>
      ) : (
        <button type="button" className={s.tap} onClick={() => setPressed(true)}>
          <StampIcon size={36} />
          {t("explore.stamp.tap")}
        </button>
      )}
      {pressed && <CheckInDates checkIn={checkIn} />}
    </div>
  );
}
