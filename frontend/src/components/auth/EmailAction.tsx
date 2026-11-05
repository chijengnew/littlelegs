"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { z } from "zod";
import {
  PASSWORD_MAX, PASSWORD_MIN, authErrorKey, firebaseErrorCode, nextFromContinueUrl, safeErrorCode, withNext,
} from "@/lib/authFlow";
import { getFirebaseAuth } from "@/lib/firebaseClient";
import { useAuth } from "../AuthProvider";
import ui from "../ui.module.css";
import s from "./auth.module.css";

type State =
  | { kind: "working" }
  | { kind: "verified"; signedIn: boolean }
  | { kind: "reset"; email: string }
  | { kind: "resetDone" }
  | { kind: "error"; message: string; retry: "verify" | "reset" }
  | { kind: "unsupported" };

export default function EmailAction() {
  const t = useTranslations();
  const auth = useAuth();
  const params = useSearchParams();
  const mode = params.get("mode");
  const oobCode = params.get("oobCode");
  const continueUrlParam = params.get("continueUrl");
  const [state, setState] = useState<State>(() => {
    if (!oobCode) return { kind: "error", retry: mode === "resetPassword" ? "reset" : "verify", message: t("auth.missingLink") };
    return mode === "verifyEmail" || mode === "resetPassword" ? { kind: "working" } : { kind: "unsupported" };
  });
  const [next, setNext] = useState("/");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const started = useRef(false);
  const { refresh } = auth;

  function fail(e: unknown, retry: "verify" | "reset", stage: string) {
    const code = firebaseErrorCode(e);
    const key = code === "auth/user-not-found" ? "auth.errors.invalidLink" : authErrorKey(code);
    setState({ kind: "error", retry, message: key ? t(key) : `${t("auth.loginFailed")} ${t("auth.errorCode", { code: safeErrorCode(e, stage) })}` });
  }

  useEffect(() => {
    if (started.current || !auth.configured || state.kind !== "working" || !oobCode) return;
    started.current = true;
    (async () => {
      const instance = await getFirebaseAuth();
      setNext(nextFromContinueUrl(continueUrlParam, window.location.origin));
      const { applyActionCode, verifyPasswordResetCode } = await import("firebase/auth");
      if (mode === "verifyEmail") {
        await instance.authStateReady();
        await applyActionCode(instance, oobCode);
        const signedIn = Boolean(instance.currentUser);
        if (signedIn) await refresh().catch(() => {});
        setState({ kind: "verified", signedIn });
      } else {
        setState({ kind: "reset", email: await verifyPasswordResetCode(instance, oobCode) });
      }
    })().catch((e) => fail(e, mode === "resetPassword" ? "reset" : "verify", "ACTION"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.configured]);

  async function submitReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !oobCode) return;
    const parsed = z
      .object({ password: z.string().min(PASSWORD_MIN, t("auth.passwordTooShort", { min: PASSWORD_MIN })).max(PASSWORD_MAX), confirm: z.string() })
      .refine((v) => v.password === v.confirm, { message: t("auth.passwordMismatch") })
      .safeParse({ password, confirm });
    if (!parsed.success) {
      setFormError(parsed.error.issues[0].message);
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      const instance = await getFirebaseAuth();
      const { confirmPasswordReset } = await import("firebase/auth");
      await confirmPasswordReset(instance, oobCode, parsed.data.password);
      setState({ kind: "resetDone" });
    } catch (e) {
      const key = authErrorKey(firebaseErrorCode(e));
      if (key === "auth.errors.expiredLink" || key === "auth.errors.invalidLink") fail(e, "reset", "RESET");
      else setFormError(key ? t(key) : `${t("auth.loginFailed")} ${t("auth.errorCode", { code: safeErrorCode(e, "RESET") })}`);
    } finally {
      setPassword("");
      setConfirm("");
      setBusy(false);
    }
  }

  let title = t(mode === "resetPassword" ? "auth.resetTitle" : "auth.verifyTitle");
  let body: ReactNode;
  if (!auth.configured) body = <p className={ui.bannerWarn} role="status">{t("auth.disabledFeature")}</p>;
  else if (state.kind === "working") body = <p className={s.lead} role="status">{t("auth.processingLink")}</p>;
  else if (state.kind === "verified") {
    body = (
      <>
        <p className={ui.bannerOk} role="status">{t(state.signedIn ? "auth.emailVerified" : "auth.emailVerifiedSignIn")}</p>
        <div className={s.actions}>
          <Link className={ui.primary} href={state.signedIn ? next : withNext("/login", next)}>
            {t(state.signedIn ? "auth.continue" : "auth.toLogin")}
          </Link>
        </div>
      </>
    );
  } else if (state.kind === "reset") {
    body = (
      <form onSubmit={submitReset} className={s.form} noValidate>
        <p className={s.lead}>{t("auth.resetFor", { email: state.email })}</p>
        <input type="email" autoComplete="username" value={state.email} readOnly hidden />
        <div>
          <label htmlFor="reset-password" className={ui.label}>{t("auth.newPassword")}</label>
          <input id="reset-password" className={ui.input} type="password" autoComplete="new-password" required autoFocus
            minLength={PASSWORD_MIN} aria-describedby="reset-password-hint"
            value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy} />
          <p className={ui.hint} id="reset-password-hint">{t("auth.passwordHint", { min: PASSWORD_MIN })}</p>
        </div>
        <div>
          <label htmlFor="reset-confirm" className={ui.label}>{t("auth.confirmPassword")}</label>
          <input id="reset-confirm" className={ui.input} type="password" autoComplete="new-password" required
            value={confirm} onChange={(e) => setConfirm(e.target.value)} disabled={busy} />
        </div>
        {formError && <p className={ui.error} role="alert">{formError}</p>}
        <button className={`${ui.primary} ${ui.block}`} type="submit" disabled={busy} aria-busy={busy}>
          {busy ? t("auth.submitting") : t("auth.resetSubmit")}
        </button>
      </form>
    );
  } else if (state.kind === "resetDone") {
    body = (
      <>
        <p className={ui.bannerOk} role="status">{t("auth.resetDone")}</p>
        <div className={s.actions}>
          <Link className={ui.primary} href={withNext("/login", next)}>{t("auth.toLogin")}</Link>
        </div>
      </>
    );
  } else if (state.kind === "error") {
    body = (
      <>
        <p className={ui.bannerError} role="alert">{state.message}</p>
        <div className={s.actions}>
          <Link className={ui.soft} href={withNext(state.retry === "reset" ? "/forgot-password" : "/verify-email", next)}>
            {t(state.retry === "reset" ? "auth.requestNewReset" : "auth.requestNewVerify")}
          </Link>
        </div>
        {state.retry === "verify" && (
          <p className={ui.hint} style={{ margin: 0 }}>
            {t("auth.verifyLinkGone")} <Link href={withNext("/register", next)}>{t("auth.toRegister")}</Link>
          </p>
        )}
      </>
    );
  } else {
    title = t("auth.verifyTitle");
    body = <p className={ui.bannerWarn} role="status">{t("auth.unsupportedLink")}</p>;
  }

  return (
    <div className={s.wrap}>
      <section className={ui.card}>
        <h1 className={s.title}>{title}</h1>
        <div style={{ display: "grid", gap: 12, marginTop: 12 }}>{body}</div>
      </section>
    </div>
  );
}
