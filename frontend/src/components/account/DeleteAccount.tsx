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
import PasswordInput from "../auth/PasswordInput";
import ui from "../ui.module.css";
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
  const dialog = useRef<HTMLDialogElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);

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

  const hasPassword = providers?.includes("password") ?? false;
  const hasGoogle = providers?.includes("google.com") ?? false;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (hasPassword) {
      if (password) run("password");
    } else if (hasGoogle) run("google");
  }

  function openDialog() {
    setOpen(true);
    dialog.current?.showModal();
    cancel.current?.focus();
  }

  function reset() {
    setOpen(false);
    setAck(false);
    setPassword("");
    setError(null);
  }

  const method = hasPassword ? "password" : "google";
  const ready = ack && !busy && (method === "google" || Boolean(password));

  return (
    <section className={`${ui.card} ${s.danger}`} aria-labelledby="delete-account">
      <h2 className={`${ui.cardTitle} ${s.dangerTitle}`} id="delete-account">{t("deleteAccount.title")}</h2>
      <p className={s.dangerIntro}>{t("deleteAccount.intro")}</p>
      <button type="button" className={ui.dangerOutline} onClick={openDialog} aria-haspopup="dialog">
        {t("deleteAccount.start")}
      </button>

      <dialog
        ref={dialog}
        className={s.dialog}
        aria-labelledby="delete-dialog-title"
        aria-describedby="delete-dialog-list"
        onCancel={(e) => {
          if (busy) e.preventDefault();
        }}
        onClose={reset}
      >
        <form className={s.dialogBody} onSubmit={submit} noValidate>
          <h2 className={s.dialogTitle} id="delete-dialog-title">{t("deleteAccount.dialogTitle")}</h2>
          <div id="delete-dialog-list" className={s.dialogList}>
            <p>{t("deleteAccount.listTitle")}</p>
            <ul>
              <li>{t("deleteAccount.listAccount")}</li>
              <li>{t("deleteAccount.listSaved")}</li>
              <li>{t("deleteAccount.listPlaces")}</li>
            </ul>
          </div>
          <label className={s.ack}>
            <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} disabled={busy} />
            {t("deleteAccount.ack")}
          </label>
          {open && providers === null && <p className={ui.hint} role="status">{t("deleteAccount.loadingMethods")}</p>}
          {providers !== null && (
            <p className={ui.hint} style={{ margin: 0 }}>{t(method === "password" ? "deleteAccount.reauthHint" : "deleteAccount.googleHint")}</p>
          )}
          {hasPassword && (
            <div>
              <label htmlFor="delete-password" className={ui.label}>{t("deleteAccount.password")}</label>
              <PasswordInput id="delete-password" autoComplete="current-password"
                value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy || !ack} />
            </div>
          )}
          {error && <p className={ui.error} role="alert">{error}</p>}
          <div className={s.dialogActions}>
            <button ref={cancel} type="button" className={ui.secondary} onClick={() => dialog.current?.close()} disabled={busy}>
              {t("deleteAccount.cancel")}
            </button>
            <button type="submit" className={ui.danger} disabled={!ready || providers === null} aria-busy={busy}>
              {busy ? t("deleteAccount.deleting") : t("deleteAccount.submit")}
            </button>
          </div>
          {hasPassword && hasGoogle && (
            <button type="button" className={`${ui.navLink} ${s.dialogAlt}`} onClick={() => run("google")} disabled={busy || !ack}>
              {t("deleteAccount.useGoogle")}
            </button>
          )}
        </form>
      </dialog>
    </section>
  );
}
