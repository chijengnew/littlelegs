"use client";

import { useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { PASSWORD_MAX, PASSWORD_MIN, authErrorKey, firebaseErrorCode, safeErrorCode, withNext } from "@/lib/authFlow";
import { getFirebaseAuth } from "@/lib/firebaseClient";
import GoogleButton from "./GoogleButton";
import { continueUrl, useAuthPage } from "./useAuthPage";
import PasswordInput from "./PasswordInput";
import { legalLinks } from "./legalLinks";
import ui from "../ui.module.css";
import s from "./auth.module.css";

export default function RegisterForm() {
  const t = useTranslations();
  const [busy, setBusy] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [inUse, setInUse] = useState(false);
  const { auth, next, router } = useAuthPage({ hold: busy, memberTarget: inUse ? "/account?tab=account" : undefined });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const lock = useRef(false);
  const waiting = busy || googleBusy || auth.pending;

  const schema = z.object({
    email: z.email(t("auth.invalidEmailForm")),
    password: z.string().min(PASSWORD_MIN, t("auth.passwordTooShort", { min: PASSWORD_MIN })).max(PASSWORD_MAX),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current || waiting) return;
    const parsed = schema.safeParse({ email: email.trim(), password });
    if (!parsed.success) {
      setError(parsed.error.issues[0].message);
      return;
    }
    lock.current = true;
    setBusy(true);
    setError(null);
    setInUse(false);
    let stage = "INIT";
    try {
      const instance = await getFirebaseAuth();
      stage = "LOAD_SDK";
      const { createUserWithEmailAndPassword, sendEmailVerification } = await import("firebase/auth");
      stage = "CREATE";
      const { user } = await createUserWithEmailAndPassword(instance, parsed.data.email, parsed.data.password);
      stage = "SEND_VERIFICATION";
      await sendEmailVerification(user, { url: continueUrl("/verify-email", next) });
      router.replace(withNext("/verify-email", next));
    } catch (e) {
      const code = firebaseErrorCode(e);
      if (code === "auth/email-already-in-use") setInUse(true);
      else {
        const key = authErrorKey(code);
        setError(key ? t(key) : `${t("auth.loginFailed")} ${t("auth.errorCode", { code: safeErrorCode(e, stage) })}`);
      }
      if (stage === "SEND_VERIFICATION") router.replace(withNext("/verify-email", next));
    } finally {
      setPassword("");
      setBusy(false);
      lock.current = false;
    }
  }

  if (!auth.configured) {
    return (
      <div className={s.wrap}>
        <h1 className={s.title}>{t("auth.registerTitle")}</h1>
        <p className={ui.bannerWarn} role="status">{t("auth.disabledFeature")}</p>
      </div>
    );
  }

  return (
    <div className={s.wrap}>
      <section className={ui.card}>
        <h1 className={s.title}>{t("auth.registerTitle")}</h1>
        <p className={s.lead}>
          {t.rich("auth.registerTerms", legalLinks)}
        </p>
        {inUse && (
          <div className={ui.bannerInfo} role="alert" style={{ marginTop: 16 }}>
            <div>
              {t("auth.emailInUseHelp")}
              <div className={s.actions}>
                <Link href={withNext("/forgot-password", next)}>{t("auth.forgot")}</Link>
              </div>
            </div>
          </div>
        )}
        <div className={s.google}>
          <GoogleButton disabled={waiting} onBusy={setGoogleBusy} />
        </div>
        <p className={s.or}>{t("auth.or")}</p>
        <form onSubmit={submit} className={s.form} noValidate>
          <div>
            <label htmlFor="reg-email" className={ui.label}>{t("auth.email")}</label>
            <input id="reg-email" className={ui.input} type="email" autoComplete="email" required autoFocus
              value={email} onChange={(e) => setEmail(e.target.value)} disabled={waiting} />
          </div>
          <div>
            <label htmlFor="reg-password" className={ui.label}>{t("auth.password")}</label>
            <PasswordInput id="reg-password" autoComplete="new-password" required minLength={PASSWORD_MIN}
              value={password} onChange={(e) => setPassword(e.target.value)} disabled={waiting} />
          </div>
          {error && <p className={ui.error} role="alert">{error}</p>}
          <p className={ui.hint} style={{ margin: 0 }}>{t("auth.registerDescription")}</p>
          <button className={`${ui.primary} ${ui.block}`} type="submit" disabled={waiting} aria-busy={busy}>
            {busy ? t("auth.submitting") : t("auth.registerSubmit")}
          </button>
        </form>
        <p className={s.switch}>
          {t("auth.haveAccount")} <Link href={withNext("/login", next)}>{t("auth.toLogin")}</Link>
        </p>
      </section>
    </div>
  );
}
