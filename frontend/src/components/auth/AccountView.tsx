"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { PASSWORD_MAX, PASSWORD_MIN, authErrorKey, firebaseErrorCode, safeErrorCode } from "@/lib/authFlow";
import { getFirebaseAuth } from "@/lib/firebaseClient";
import { useAuth } from "../AuthProvider";
import DeleteAccount from "../account/DeleteAccount";
import MemberGate from "../account/MemberGate";
import SavedList from "../account/SavedList";
import SignOutButton from "./SignOutButton";
import ui from "../ui.module.css";
import s from "./auth.module.css";

const TABS = ["history", "favorites", "account"] as const;
type Tab = (typeof TABS)[number];
type Profile = { email: string | null; emailVerified: boolean; providers: string[] };

export default function AccountView() {
  const t = useTranslations();
  const router = useRouter();
  const params = useSearchParams();
  const requested = params.get("tab");
  const tab: Tab = TABS.includes(requested as Tab) ? (requested as Tab) : "account";
  const deleted = params.get("deleted");

  return (
    <div className={s.wide}>
      <h1 className={s.title}>{t("auth.accountTitle")}</h1>
      <MemberGate next="/account">
        {deleted && (
          <p className={ui.bannerOk} role="status" style={{ marginBottom: 12 }}>
            {t(deleted === "accepted" ? "saved.deleteAccepted" : "saved.deleted")}
          </p>
        )}
        <div className={s.tabs} role="tablist" aria-label={t("auth.accountTitle")}>
          {TABS.map((k) => (
            <button key={k} type="button" role="tab" id={`tab-${k}`} aria-selected={tab === k} aria-controls="account-panel"
              className={tab === k ? s.tabActive : s.tab} onClick={() => router.replace(`/account?tab=${k}`, { scroll: false })}>
              {t(k === "history" ? "auth.tabHistory" : k === "favorites" ? "auth.tabFavorites" : "auth.tabAccount")}
            </button>
          ))}
        </div>
        <div id="account-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
          {tab === "history" && <SavedList kind="history" />}
          {tab === "favorites" && <SavedList kind="favorite" />}
          {tab === "account" && <><AccountTab /><DeleteAccount /></>}
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
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const lock = useRef(false);

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
      .object({ password: z.string().min(PASSWORD_MIN, t("auth.passwordTooShort", { min: PASSWORD_MIN })).max(PASSWORD_MAX), confirm: z.string() })
      .refine((v) => v.password === v.confirm, { message: t("auth.passwordMismatch") })
      .safeParse({ password, confirm });
    if (!parsed.success) {
      setNotice({ ok: false, text: parsed.error.issues[0].message });
      return;
    }
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
      setConfirm("");
      setBusy(false);
      lock.current = false;
    }
  }

  const hasPassword = profile?.providers.includes("password") ?? false;
  const hasGoogle = profile?.providers.includes("google.com") ?? false;
  const methods = [hasPassword && t("auth.providerPassword"), hasGoogle && t("auth.providerGoogle")].filter(Boolean).join("、");

  return (
    <section className={ui.card} style={{ marginTop: 12 }}>
      <dl className={s.details}>
        <dt>{t("auth.emailLabel")}</dt><dd>{profile?.email ?? "—"}</dd>
        <dt>{t("auth.emailVerification")}</dt><dd>{profile ? t(profile.emailVerified ? "auth.verifiedYes" : "auth.verifiedNo") : "—"}</dd>
        <dt>{t("auth.signInMethods")}</dt><dd>{methods || "—"}</dd>
        <dt>{t("auth.memberId")}</dt><dd>{member?.id}</dd>
      </dl>
      {hasGoogle && !hasPassword && (
        <form onSubmit={addPassword} className={s.form} noValidate>
          <h2 className={ui.cardTitle} style={{ margin: 0 }}>{t("auth.addPassword")}</h2>
          <p className={ui.hint}>{t("auth.addPasswordHint")}</p>
          <input type="email" autoComplete="username" value={profile?.email ?? ""} readOnly hidden />
          <div>
            <label htmlFor="add-password" className={ui.label}>{t("auth.newPassword")}</label>
            <input id="add-password" className={ui.input} type="password" autoComplete="new-password" required
              minLength={PASSWORD_MIN} aria-describedby="add-password-hint"
              value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy} />
            <p className={ui.hint} id="add-password-hint">{t("auth.passwordHint", { min: PASSWORD_MIN })}</p>
          </div>
          <div>
            <label htmlFor="add-confirm" className={ui.label}>{t("auth.confirmPassword")}</label>
            <input id="add-confirm" className={ui.input} type="password" autoComplete="new-password" required
              value={confirm} onChange={(e) => setConfirm(e.target.value)} disabled={busy} />
          </div>
          <button className={ui.primary} type="submit" disabled={busy} aria-busy={busy}>
            {busy ? t("auth.submitting") : t("auth.addPasswordSubmit")}
          </button>
        </form>
      )}
      {notice && <p className={notice.ok ? ui.bannerOk : ui.bannerError} role="status" style={{ marginTop: 12 }}>{notice.text}</p>}
      <div className={s.actions} style={{ marginTop: 16 }}>
        <SignOutButton />
      </div>
    </section>
  );
}
