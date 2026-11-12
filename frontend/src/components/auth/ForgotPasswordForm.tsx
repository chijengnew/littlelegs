"use client";

import { useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { authErrorKey, firebaseErrorCode, safeErrorCode, withNext } from "@/lib/authFlow";
import { getFirebaseAuth } from "@/lib/firebaseClient";
import { continueUrl, useAuthPage } from "./useAuthPage";
import { ArrowLeftIcon, MailIcon } from "../icons";
import ui from "../ui.module.css";
import s from "./auth.module.css";

const QUIET = new Set(["auth/user-not-found", "auth/invalid-credential"]);

export default function ForgotPasswordForm() {
  const t = useTranslations();
  const { auth, next } = useAuthPage();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lock = useRef(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current || busy) return;
    const parsed = z.email().safeParse(email.trim());
    if (!parsed.success) {
      setError(t("auth.invalidEmailForm"));
      return;
    }
    lock.current = true;
    setBusy(true);
    setError(null);
    let stage = "INIT";
    try {
      const instance = await getFirebaseAuth();
      stage = "LOAD_SDK";
      const { sendPasswordResetEmail } = await import("firebase/auth");
      stage = "SEND_RESET";
      await sendPasswordResetEmail(instance, parsed.data, { url: continueUrl("/login", next) });
      setSent(true);
    } catch (e) {
      const code = firebaseErrorCode(e);
      if (code && QUIET.has(code)) setSent(true);
      else {
        const key = authErrorKey(code);
        setError(key ? t(key) : `${t("auth.loginFailed")} ${t("auth.errorCode", { code: safeErrorCode(e, stage) })}`);
      }
    } finally {
      setBusy(false);
      lock.current = false;
    }
  }

  if (!auth.configured) {
    return (
      <div className={s.wrap}>
        <h1 className={s.title}>{t("auth.forgotTitle")}</h1>
        <p className={ui.bannerWarn} role="status">{t("auth.disabledFeature")}</p>
      </div>
    );
  }

  return (
    <div className={s.wrap}>
      <section className={ui.card}>
        <span className={s.stateIcon} aria-hidden="true"><MailIcon size={28} /></span>
        <h1 className={s.title}>{t("auth.forgotTitle")}</h1>
        <p className={s.lead}>{t("auth.forgotDescription")}</p>
        <p className={ui.hint}>{t("auth.forgotGoogle")}</p>
        {sent ? (
          <p className={`${ui.bannerOk} ${s.notice}`} role="status">{t("auth.forgotSent")}</p>
        ) : (
          <form onSubmit={submit} className={s.form} noValidate>
            <div>
              <label htmlFor="forgot-email" className={ui.label}>{t("auth.email")}</label>
              <input id="forgot-email" className={ui.input} type="email" autoComplete="username" required autoFocus
                value={email} onChange={(e) => setEmail(e.target.value)} disabled={busy} />
            </div>
            {error && <p className={ui.error} role="alert">{error}</p>}
            <button className={`${ui.primary} ${ui.block}`} type="submit" disabled={busy} aria-busy={busy}>
              {busy ? t("auth.submitting") : t("auth.forgotSubmit")}
            </button>
          </form>
        )}
        <p className={s.backRow}>
          <Link className={ui.navLink} href={withNext("/login", next)}>
            <ArrowLeftIcon className={ui.arrowStart} />
            {t("auth.backToLogin")}
          </Link>
        </p>
      </section>
    </div>
  );
}
