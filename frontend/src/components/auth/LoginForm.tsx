"use client";

import { useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { authErrorKey, firebaseErrorCode, safeErrorCode, withNext } from "@/lib/authFlow";
import { getFirebaseAuth } from "@/lib/firebaseClient";
import GoogleButton from "./GoogleButton";
import SignOutButton from "./SignOutButton";
import { useAuthPage } from "./useAuthPage";
import PasswordInput from "./PasswordInput";
import { legalLinks } from "./legalLinks";
import ui from "../ui.module.css";
import s from "./auth.module.css";

const schema = z.object({ email: z.email(), password: z.string().min(1) });

export default function LoginForm() {
  const t = useTranslations();
  const { auth, next } = useAuthPage();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lock = useRef(false);
  const waiting = busy || googleBusy || auth.pending;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current || waiting) return;
    const parsed = schema.safeParse({ email: email.trim(), password });
    if (!parsed.success) {
      setError(t(parsed.error.issues[0].path[0] === "email" ? "auth.invalidEmailForm" : "auth.passwordRequired"));
      return;
    }
    lock.current = true;
    setBusy(true);
    setError(null);
    let stage = "INIT";
    try {
      const instance = await getFirebaseAuth();
      const previousUid = instance.currentUser?.uid;
      stage = "LOAD_SDK";
      const { signInWithEmailAndPassword } = await import("firebase/auth");
      stage = "SIGN_IN";
      const credential = await signInWithEmailAndPassword(instance, parsed.data.email, parsed.data.password);
      if (previousUid === credential.user.uid) auth.retry();
    } catch (e) {
      const key = authErrorKey(firebaseErrorCode(e));
      setError(key ? t(key) : `${t("auth.loginFailed")} ${t("auth.errorCode", { code: safeErrorCode(e, stage) })}`);
    } finally {
      setPassword("");
      setBusy(false);
      lock.current = false;
    }
  }

  if (!auth.configured) {
    return (
      <div className={s.wrap}>
        <h1 className={s.title}>{t("auth.loginTitle")}</h1>
        <p className={ui.bannerWarn} role="status">{t("auth.disabledFeature")}</p>
      </div>
    );
  }

  return (
    <div className={s.wrap}>
      <section className={ui.card}>
        <h1 className={s.title}>{t("auth.loginTitle")}</h1>
        {auth.user && auth.error && (
          <div className={ui.bannerError} role="alert" style={{ marginTop: 16 }}>
            <div>
              {auth.error.message}
              <p className={ui.hint}>{t("auth.errorCode", { code: auth.error.code })}</p>
              <div className={s.actions}>
                <button type="button" className={ui.soft} onClick={auth.retry}>{t("auth.retryVerification")}</button>
                <SignOutButton />
              </div>
            </div>
          </div>
        )}
        <div className={s.google}>
          <GoogleButton disabled={waiting} onBusy={setGoogleBusy} />
          <p className={s.terms}>
            {t.rich("auth.loginTerms", legalLinks)}
          </p>
        </div>
        <p className={s.or}>{t("auth.or")}</p>
        <form onSubmit={submit} className={s.form} noValidate>
          <div>
            <label htmlFor="login-email" className={ui.label}>{t("auth.email")}</label>
            <input id="login-email" className={ui.input} type="email" autoComplete="username" required autoFocus
              value={email} onChange={(e) => setEmail(e.target.value)} disabled={waiting} />
          </div>
          <div>
            <label htmlFor="login-password" className={ui.label}>{t("auth.password")}</label>
            <PasswordInput id="login-password" autoComplete="current-password" required
              value={password} onChange={(e) => setPassword(e.target.value)} disabled={waiting} />
            <p className={s.forgot}>
              <Link href={withNext("/forgot-password", next)}>{t("auth.forgot")}</Link>
            </p>
          </div>
          {error && <p className={ui.error} role="alert">{error}</p>}
          <button className={`${ui.primary} ${ui.block}`} type="submit" disabled={waiting} aria-busy={busy}>
            {busy || (auth.user && auth.pending) ? t("auth.verifying") : t("auth.submit")}
          </button>
        </form>
        <p className={s.switch}>
          {t("auth.noAccount")} <Link href={withNext("/register", next)}>{t("auth.toRegister")}</Link>
        </p>
      </section>
    </div>
  );
}
