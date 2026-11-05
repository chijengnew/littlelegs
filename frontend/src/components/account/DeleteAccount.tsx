"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import { authErrorKey, firebaseErrorCode, safeErrorCode } from "@/lib/authFlow";
import { getFirebaseAuth } from "@/lib/firebaseClient";
import { clearFlow } from "@/lib/flowStorage";
import { uuidv7 } from "@/lib/ids";
import ui from "../ui.module.css";
import a from "../auth/auth.module.css";
import s from "./account.module.css";

const keyName = (uid: string) => `littlelegs:delete-account:${uid}`;
function deletionKey(uid: string): string {
  try {
    const saved = sessionStorage.getItem(keyName(uid));
    if (saved) return saved;
    const key = uuidv7();
    sessionStorage.setItem(keyName(uid), key);
    return key;
  } catch {
    return uuidv7();
  }
}
function clearDeletionKey(uid: string) {
  try {
    sessionStorage.removeItem(keyName(uid));
  } catch {
  }
}

export default function DeleteAccount() {
  const t = useTranslations();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [ack, setAck] = useState(false);
  const [password, setPassword] = useState("");
  const [providers, setProviders] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lock = useRef(false);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    getFirebaseAuth().then((instance) => {
      if (alive) setProviders(instance.currentUser?.providerData.map((p) => p.providerId) ?? []);
    }, () => { if (alive) setProviders([]); });
    return () => { alive = false; };
  }, [open]);

  async function run(method: "password" | "google") {
    if (lock.current || !ack) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    let stage = "INIT";
    try {
      const instance = await getFirebaseAuth();
      const user = instance.currentUser;
      if (!user) return;
      stage = "LOAD_SDK";
      const fa = await import("firebase/auth");
      stage = "REAUTH";
      if (method === "password") {
        await fa.reauthenticateWithCredential(user, fa.EmailAuthProvider.credential(user.email ?? "", password));
      } else {
        await fa.reauthenticateWithPopup(user, new fa.GoogleAuthProvider());
      }
      stage = "TOKEN";
      await user.getIdToken(true);
      stage = "DELETE";
      const uid = user.uid;
      const { data, error: problem, response } = await api.DELETE("/v1/me", {
        params: { header: { "Idempotency-Key": deletionKey(uid) } },
      });
      if (!data) {
        setError(problem?.code === "DELETION_RESULT_UNKNOWN" ? t("deleteAccount.unknown") : toUiError(t, problem, response.status).message);
        return;
      }
      clearDeletionKey(uid);
      clearFlow();
      await fa.signOut(instance).catch(() => {});
      router.replace(data.status === "completed" ? "/account/deleted" : "/account/deleted?status=accepted");
    } catch (e) {
      const key = authErrorKey(firebaseErrorCode(e));
      setError(key ? t(key) : `${t("deleteAccount.failed")} ${t("auth.errorCode", { code: safeErrorCode(e, stage) })}`);
    } finally {
      setPassword("");
      setBusy(false);
      lock.current = false;
    }
  }

  function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password) run("password");
  }

  const hasPassword = providers?.includes("password") ?? false;
  const hasGoogle = providers?.includes("google.com") ?? false;

  return (
    <section className={`${ui.card} ${s.section}`} aria-labelledby="delete-account">
      <h2 className={ui.cardTitle} id="delete-account">{t("deleteAccount.title")}</h2>
      <p className={ui.hint} style={{ marginTop: 0 }}>{t("deleteAccount.intro")}</p>
      {!open ? (
        <button type="button" className={ui.secondary} onClick={() => setOpen(true)}>{t("deleteAccount.start")}</button>
      ) : (
        <div className={a.form} style={{ marginTop: 0 }}>
          <label className={a.links} style={{ justifyContent: "flex-start", gap: 8 }}>
            <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} disabled={busy} />
            {t("deleteAccount.ack")}
          </label>
          <p className={ui.hint} style={{ margin: 0 }}>{t("deleteAccount.reauthHint")}</p>
          {hasPassword && (
            <form onSubmit={submitPassword} className={a.form} style={{ marginTop: 0 }} noValidate>
              <div>
                <label htmlFor="delete-password" className={ui.label}>{t("deleteAccount.password")}</label>
                <input id="delete-password" className={ui.input} type="password" autoComplete="current-password"
                  value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy || !ack} />
              </div>
              <button type="submit" className={ui.danger} disabled={busy || !ack || !password} aria-busy={busy}>
                {busy ? t("deleteAccount.deleting") : t("deleteAccount.submitPassword")}
              </button>
            </form>
          )}
          {hasGoogle && (
            <button type="button" className={ui.danger} onClick={() => run("google")} disabled={busy || !ack} aria-busy={busy}>
              {busy ? t("deleteAccount.deleting") : t("deleteAccount.submitGoogle")}
            </button>
          )}
          {error && <p className={ui.error} role="alert">{error}</p>}
          <button type="button" className={ui.soft} onClick={() => { setOpen(false); setAck(false); setError(null); }} disabled={busy}
            style={{ justifySelf: "start" }}>
            {t("deleteAccount.cancel")}
          </button>
        </div>
      )}
    </section>
  );
}
