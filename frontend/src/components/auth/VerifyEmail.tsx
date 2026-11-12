"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import { authErrorKey, firebaseErrorCode, safeErrorCode, withNext } from "@/lib/authFlow";
import { getFirebaseAuth } from "@/lib/firebaseClient";
import { SkeletonCard } from "../Skeleton";
import SignOutButton from "./SignOutButton";
import { continueUrl, useAuthPage } from "./useAuthPage";
import { MailIcon } from "../icons";
import ui from "../ui.module.css";
import s from "./auth.module.css";

const RESEND_COOLDOWN_S = 60;

export default function VerifyEmail() {
  const t = useTranslations();
  const { auth, next, router } = useAuthPage({ verifyPage: true });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const lock = useRef(false);
  const { refresh, unverified } = auth;

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((n) => n - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  useEffect(() => {
    if (!unverified) return;
    const onFocus = () => { if (document.visibilityState === "visible") refresh().catch(() => {}); };
    document.addEventListener("visibilitychange", onFocus);
    return () => document.removeEventListener("visibilitychange", onFocus);
  }, [unverified, refresh]);

  async function resend() {
    if (lock.current || cooldown > 0) return;
    lock.current = true;
    setBusy(true);
    setNotice(null);
    try {
      const instance = await getFirebaseAuth();
      const { sendEmailVerification } = await import("firebase/auth");
      if (!instance.currentUser) return;
      await sendEmailVerification(instance.currentUser, { url: continueUrl("/verify-email", next) });
      setNotice({ ok: true, text: t("auth.resent") });
      setCooldown(RESEND_COOLDOWN_S);
    } catch (e) {
      const key = authErrorKey(firebaseErrorCode(e));
      setNotice({ ok: false, text: key ? t(key) : `${t("auth.loginFailed")} ${t("auth.errorCode", { code: safeErrorCode(e, "SEND_VERIFICATION") })}` });
    } finally {
      setBusy(false);
      lock.current = false;
    }
  }

  async function check() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setNotice(null);
    try {
      await refresh();
      const instance = await getFirebaseAuth();
      if (!instance.currentUser?.emailVerified) setNotice({ ok: false, text: t("auth.stillUnverified") });
    } catch (e) {
      setNotice({ ok: false, text: `${t("auth.loginFailed")} ${t("auth.errorCode", { code: safeErrorCode(e, "RELOAD") })}` });
    } finally {
      setBusy(false);
      lock.current = false;
    }
  }

  async function cancelRegistration() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setNotice(null);
    let stage = "CANCEL";
    try {
      const { error, response } = await api.DELETE("/v1/me/registration");
      if (error?.code === "REGISTRATION_COMPLETED") {
        setNotice({ ok: true, text: t("auth.alreadyVerified") });
        await refresh();
        return;
      }
      if (response.status !== 204 && error?.code !== "AUTH_REAUTH_REQUIRED") {
        setNotice({ ok: false, text: `${t("auth.cancelFailed")} ${toUiError(t, error, response.status).message}` });
        return;
      }
      setLeaving(true);
      stage = "SIGN_OUT";
      const instance = await getFirebaseAuth();
      const { signOut } = await import("firebase/auth");
      await signOut(instance);
      router.replace(next);
    } catch (e) {
      setLeaving(false);
      const text = stage === "CANCEL" ? toUiError(t, e).message : t("auth.errorCode", { code: safeErrorCode(e, stage) });
      setNotice({ ok: false, text: `${t("auth.cancelFailed")} ${text}` });
    } finally {
      setConfirming(false);
      setBusy(false);
      lock.current = false;
    }
  }

  let body: ReactNode;
  if (!auth.configured) body = <p className={ui.bannerWarn} role="status">{t("auth.disabledFeature")}</p>;
  else if (leaving) body = <p className={ui.bannerOk} role="status">{t("auth.cancelled")}</p>;
  else if (!auth.booted || auth.pending) body = <SkeletonCard lines={2} />;
  else if (!auth.user) {
    body = (
      <p className={s.lead}>
        {t("auth.needLogin")} <Link href={withNext("/login", next)}>{t("auth.toLogin")}</Link>
      </p>
    );
  } else if (auth.member) {
    body = <p className={ui.bannerOk} role="status">{t("auth.verifiedDone")}</p>;
  } else if (auth.error) {
    body = (
      <div className={ui.bannerError} role="alert">
        <div>
          {auth.error.message}
          <div className={s.actions}>
            <button type="button" className={ui.soft} onClick={auth.retry}>{t("auth.retryVerification")}</button>
            <SignOutButton to={withNext("/login", next)} />
          </div>
        </div>
      </div>
    );
  } else {
    body = (
      <>
        <p className={s.lead}>{t("auth.verifySent", { email: auth.user.email ?? "" })}</p>
        <p className={ui.hint} style={{ margin: 0 }}>{t("auth.pendingRule")}</p>
        {notice && <p className={notice.ok ? ui.bannerOk : ui.bannerWarn} role="status">{notice.text}</p>}
        <div className={s.actions}>
          <button type="button" className={ui.primary} onClick={check} disabled={busy} aria-busy={busy}>
            {t("auth.checkVerified")}
          </button>
          <button type="button" className={ui.soft} onClick={resend} disabled={busy || cooldown > 0}>
            {cooldown > 0 ? t("auth.resendIn", { s: cooldown }) : t("auth.resend")}
          </button>
        </div>
        {confirming ? (
          <div className={ui.bannerWarn} role="alertdialog" aria-labelledby="cancel-registration">
            <div>
              <p id="cancel-registration" style={{ margin: 0 }}>{t("auth.cancelConfirm")}</p>
              <div className={s.actions}>
                <button type="button" className={ui.danger} onClick={cancelRegistration} disabled={busy} aria-busy={busy}>
                  {busy ? t("auth.cancelling") : t("auth.cancelConfirmYes")}
                </button>
                <button type="button" className={ui.soft} onClick={() => setConfirming(false)} disabled={busy}>
                  {t("auth.cancelBack")}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className={s.actions} style={{ marginTop: 4 }}>
            <button type="button" className={ui.secondary} onClick={() => { setNotice(null); setConfirming(true); }} disabled={busy}>
              {t("auth.cancelRegistration")}
            </button>
            <SignOutButton to={next} />
          </div>
        )}
      </>
    );
  }

  return (
    <div className={s.wrapStatus}>
      <section className={ui.card}>
        <span className={s.stateIcon} aria-hidden="true"><MailIcon size={28} /></span>
        <h1 className={s.title}>{t("auth.verifyTitle")}</h1>
        <div className={s.stateBody}>{body}</div>
      </section>
    </div>
  );
}
