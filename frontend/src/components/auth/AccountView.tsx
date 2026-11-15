"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { PASSWORD_MAX, PASSWORD_MIN, authErrorKey, firebaseErrorCode, reauthErrorKey, safeErrorCode } from "@/lib/authFlow";
import { getFirebaseAuth } from "@/lib/firebaseClient";
import { useAuth } from "../AuthProvider";
import DeleteAccount from "../account/DeleteAccount";
import MemberGate from "../account/MemberGate";
import SavedList from "../account/SavedList";
import SignOutButton from "./SignOutButton";
import PasswordInput from "./PasswordInput";
import { CheckIcon, PencilIcon } from "../icons";
import ui from "../ui.module.css";
import s from "./auth.module.css";

const TABS = ["history", "favorites", "account"] as const;
type Tab = (typeof TABS)[number];
type Profile = { email: string | null; emailVerified: boolean; providers: string[] };

export default function AccountView() {
  const t = useTranslations();
  const params = useSearchParams();
  const requested = params.get("tab");
  const tab: Tab = TABS.includes(requested as Tab) ? (requested as Tab) : "history";
  const deleted = params.get("deleted");

  return (
    <div className={s.account}>
      <h1 className={s.title}>{t("auth.accountTitle")}</h1>
      <MemberGate next="/account">
        {deleted && (
          <p className={ui.bannerOk} role="status">
            {t(deleted === "accepted" ? "saved.deleteAccepted" : "saved.deleted")}
          </p>
        )}
        <div className={s.accountBody}>
          <nav className={s.accountNav} aria-label={t("auth.accountNav")}>
            {TABS.map((k) => (
              <Link key={k} href={`/account?tab=${k}`} scroll={false} className={s.accountLink} aria-current={tab === k ? "page" : undefined}>
                {t(k === "history" ? "auth.tabHistory" : k === "favorites" ? "auth.tabFavorites" : "auth.tabAccount")}
              </Link>
            ))}
          </nav>
          <div id="account-panel" className={s.accountPanel}>
            {tab === "history" && <SavedList kind="history" />}
            {tab === "favorites" && <SavedList kind="favorite" />}
            {tab === "account" && (
              <div className={s.settings}>
                <AccountTab />
                <DeleteAccount />
              </div>
            )}
          </div>
        </div>
      </MemberGate>
    </div>
  );
}

function AccountTab() {
  const t = useTranslations();
  const { member } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [password, setPassword] = useState("");
  const [changing, setChanging] = useState(false);
  const [current, setCurrent] = useState("");
  const [fresh, setFresh] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ add?: string; current?: string; fresh?: string }>({});
  const lock = useRef(false);

  function clearFieldError(field: "add" | "current" | "fresh") {
    setFieldErrors((f) => (f[field] ? { ...f, [field]: undefined } : f));
  }

  async function readProfile(): Promise<Profile | null> {
    const user = (await getFirebaseAuth()).currentUser;
    return user ? { email: user.email, emailVerified: user.emailVerified, providers: user.providerData.map((p) => p.providerId) } : null;
  }

  useEffect(() => {
    let alive = true;
    readProfile().then((p) => { if (alive) setProfile(p); }, () => {});
    return () => { alive = false; };
  }, [member?.id]);

  async function addPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current || busy) return;
    const parsed = z
      .object({ password: z.string().min(PASSWORD_MIN, t("auth.passwordTooShort", { min: PASSWORD_MIN })).max(PASSWORD_MAX, t("auth.passwordTooLong")) })
      .safeParse({ password });
    if (!parsed.success) {
      setFieldErrors({ add: parsed.error.issues[0].message });
      setNotice(null);
      document.getElementById("add-password")?.focus();
      return;
    }
    setFieldErrors({});
    lock.current = true;
    setBusy(true);
    setNotice(null);
    let stage = "INIT";
    try {
      const instance = await getFirebaseAuth();
      const user = instance.currentUser;
      if (!user?.email) return;
      stage = "LOAD_SDK";
      const { EmailAuthProvider, GoogleAuthProvider, linkWithCredential, reauthenticateWithPopup } = await import("firebase/auth");
      stage = "REAUTH";
      await reauthenticateWithPopup(user, new GoogleAuthProvider());
      stage = "LINK";
      await linkWithCredential(user, EmailAuthProvider.credential(user.email, parsed.data.password));
      setProfile(await readProfile());
      setNotice({ ok: true, text: t("auth.passwordAdded") });
    } catch (e) {
      const key = authErrorKey(firebaseErrorCode(e));
      setNotice({ ok: false, text: key ? t(key) : `${t("auth.loginFailed")} ${t("auth.errorCode", { code: safeErrorCode(e, stage) })}` });
    } finally {
      setPassword("");
      setBusy(false);
      lock.current = false;
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current || busy) return;
    const parsed = z.string().min(PASSWORD_MIN, t("auth.passwordTooShort", { min: PASSWORD_MIN })).max(PASSWORD_MAX, t("auth.passwordTooLong")).safeParse(fresh);
    if (!current || !parsed.success) {
      const found = {
        current: current ? undefined : t("auth.passwordRequired"),
        fresh: parsed.success ? undefined : parsed.error.issues[0].message,
      };
      setFieldErrors(found);
      setNotice(null);
      document.getElementById(found.current ? "current-password" : "change-new-password")?.focus();
      return;
    }
    setFieldErrors({});
    lock.current = true;
    setBusy(true);
    setNotice(null);
    let stage = "INIT";
    try {
      const instance = await getFirebaseAuth();
      const user = instance.currentUser;
      if (!user?.email) return;
      stage = "LOAD_SDK";
      const { EmailAuthProvider, reauthenticateWithCredential, updatePassword } = await import("firebase/auth");
      stage = "REAUTH";
      await reauthenticateWithCredential(user, EmailAuthProvider.credential(user.email, current));
      stage = "UPDATE";
      await updatePassword(user, parsed.data);
      setChanging(false);
      setNotice({ ok: true, text: t("auth.passwordChanged") });
    } catch (e) {
      const key = reauthErrorKey(firebaseErrorCode(e));
      setNotice({ ok: false, text: key ? t(key) : `${t("auth.loginFailed")} ${t("auth.errorCode", { code: safeErrorCode(e, stage) })}` });
    } finally {
      setCurrent("");
      setFresh("");
      setBusy(false);
      lock.current = false;
    }
  }

  function toggleChange() {
    setChanging((v) => !v);
    setCurrent("");
    setFresh("");
    setNotice(null);
    setFieldErrors({});
  }

  const hasPassword = profile?.providers.includes("password") ?? false;
  const hasGoogle = profile?.providers.includes("google.com") ?? false;

  return (
    <section className={`${ui.card} ${s.accountCard}`} aria-labelledby="profile-title">
      <h2 className={ui.cardTitle} id="profile-title">{t("auth.profileTitle")}</h2>
      <dl className={s.details}>
        <dt>{t("auth.emailLabel")}</dt>
        <dd className={s.emailRow}>
          <span>{profile?.email ?? "—"}</span>
          {profile && (
            <span className={profile.emailVerified ? s.verified : s.unverified}>
              {profile.emailVerified && <CheckIcon size={16} />}
              {t(profile.emailVerified ? "auth.verifiedYes" : "auth.verifiedNo")}
            </span>
          )}
        </dd>
        <dt>{t("auth.signInMethods")}</dt>
        <dd className={s.methods}>
          {hasPassword && (
            <span className={s.method}>
              {t("auth.providerPassword")}
              {!changing && (
                <button type="button" className={`${ui.navLink} ${s.methodAction}`} onClick={toggleChange}>
                  <PencilIcon size={16} />
                  {t("auth.changePassword")}
                </button>
              )}
            </span>
          )}
          {hasGoogle && <span className={s.method}>{t("auth.providerGoogle")}</span>}
          {!hasPassword && !hasGoogle && "—"}
        </dd>
      </dl>
      {hasPassword && changing && (
        <form id="change-password" onSubmit={changePassword} className={s.form} noValidate>
          <h3 className={s.subTitle}>{t("auth.changePassword")}</h3>
          <input type="email" autoComplete="username" value={profile?.email ?? ""} readOnly hidden />
          <div>
            <label htmlFor="current-password" className={ui.label}>{t("auth.currentPassword")}</label>
            <PasswordInput id="current-password" autoComplete="current-password" required autoFocus
              aria-invalid={Boolean(fieldErrors.current)} aria-describedby={fieldErrors.current ? "current-password-error" : undefined}
              value={current} onChange={(e) => { setCurrent(e.target.value); clearFieldError("current"); }} disabled={busy} />
            {fieldErrors.current && <p className={ui.error} id="current-password-error">{fieldErrors.current}</p>}
          </div>
          <div>
            <label htmlFor="change-new-password" className={ui.label}>{t("auth.newPassword")}</label>
            <PasswordInput id="change-new-password" autoComplete="new-password" required
              minLength={PASSWORD_MIN} aria-invalid={Boolean(fieldErrors.fresh)}
              aria-describedby={fieldErrors.fresh ? "change-password-error" : "change-password-hint"}
              value={fresh} onChange={(e) => { setFresh(e.target.value); clearFieldError("fresh"); }} disabled={busy} />
            {fieldErrors.fresh
              ? <p className={ui.error} id="change-password-error">{fieldErrors.fresh}</p>
              : <p className={ui.hint} id="change-password-hint">{t("auth.passwordHint", { min: PASSWORD_MIN })}</p>}
          </div>
          <div className={s.formActions}>
            <button type="button" className={ui.secondary} onClick={toggleChange} disabled={busy}>{t("auth.cancel")}</button>
            <button className={ui.primary} type="submit" disabled={busy} aria-busy={busy}>
              {busy ? t("auth.submitting") : t("auth.changePasswordSubmit")}
            </button>
          </div>
        </form>
      )}
      {hasGoogle && !hasPassword && (
        <form onSubmit={addPassword} className={s.form} noValidate>
          <h3 className={s.subTitle}>{t("auth.addPassword")}</h3>
          <p className={ui.hint}>{t("auth.addPasswordHint")}</p>
          <input type="email" autoComplete="username" value={profile?.email ?? ""} readOnly hidden />
          <div>
            <label htmlFor="add-password" className={ui.label}>{t("auth.newPassword")}</label>
            <PasswordInput id="add-password" autoComplete="new-password" required
              minLength={PASSWORD_MIN} aria-invalid={Boolean(fieldErrors.add)}
              aria-describedby={fieldErrors.add ? "add-password-error" : "add-password-hint"}
              value={password} onChange={(e) => { setPassword(e.target.value); clearFieldError("add"); }} disabled={busy} />
            {fieldErrors.add
              ? <p className={ui.error} id="add-password-error">{fieldErrors.add}</p>
              : <p className={ui.hint} id="add-password-hint">{t("auth.passwordHint", { min: PASSWORD_MIN })}</p>}
          </div>
          <button className={ui.primary} type="submit" disabled={busy} aria-busy={busy}>
            {busy ? t("auth.submitting") : t("auth.addPasswordSubmit")}
          </button>
        </form>
      )}
      {notice && <p className={`${notice.ok ? ui.bannerOk : ui.bannerError} ${s.notice}`} role="status">{notice.text}</p>}
      <div className={s.actions}>
        <SignOutButton />
      </div>
    </section>
  );
}
