"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { authErrorKey, firebaseErrorCode, safeErrorCode, shouldUseRedirect } from "@/lib/authFlow";
import { getFirebaseAuth } from "@/lib/firebaseClient";
import ui from "../ui.module.css";

export default function GoogleButton({ disabled, onBusy }: { disabled?: boolean; onBusy?: (busy: boolean) => void }) {
  const t = useTranslations();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const checked = useRef(false);

  function fail(e: unknown, stage: string) {
    const key = authErrorKey(firebaseErrorCode(e));
    if (key === "auth.errors.cancelled") return;
    setError(key ? t(key) : `${t("auth.loginFailed")} ${t("auth.errorCode", { code: safeErrorCode(e, stage) })}`);
  }

  useEffect(() => {
    if (checked.current) return;
    checked.current = true;
    (async () => {
      const auth = await getFirebaseAuth();
      const { getRedirectResult } = await import("firebase/auth");
      await getRedirectResult(auth);
    })().catch((e) => fail(e, "REDIRECT_RESULT"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function signIn() {
    if (busy) return;
    setBusy(true);
    onBusy?.(true);
    setError(null);
    let stage = "INIT";
    try {
      const auth = await getFirebaseAuth();
      stage = "LOAD_SDK";
      const { GoogleAuthProvider, signInWithPopup, signInWithRedirect } = await import("firebase/auth");
      const provider = new GoogleAuthProvider();
      provider.setCustomParameters({ prompt: "select_account" });
      stage = "SIGN_IN";
      try {
        await signInWithPopup(auth, provider);
      } catch (e) {
        if (!shouldUseRedirect(firebaseErrorCode(e))) throw e;
        stage = "REDIRECT";
        await signInWithRedirect(auth, provider);
      }
    } catch (e) {
      fail(e, stage);
    } finally {
      setBusy(false);
      onBusy?.(false);
    }
  }

  return (
    <div>
      <button type="button" className={`${ui.secondary} ${ui.block}`} onClick={signIn} disabled={disabled || busy} aria-busy={busy}>
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
          <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.4h6.5a5.6 5.6 0 0 1-2.4 3.6v3h3.9c2.3-2.1 3.5-5.2 3.5-8.7z" />
          <path fill="#34A853" d="M12 24c3.2 0 6-1.1 8-2.9l-3.9-3c-1.1.7-2.5 1.2-4.1 1.2-3.1 0-5.8-2.1-6.7-5H1.3v3.1A12 12 0 0 0 12 24z" />
          <path fill="#FBBC05" d="M5.3 14.3a7.2 7.2 0 0 1 0-4.6V6.6h-4a12 12 0 0 0 0 10.8l4-3.1z" />
          <path fill="#EA4335" d="M12 4.8c1.8 0 3.3.6 4.6 1.8l3.4-3.4A12 12 0 0 0 1.3 6.6l4 3.1c.9-2.9 3.6-4.9 6.7-4.9z" />
        </svg>
        {t("auth.google")}
      </button>
      {error && <p className={ui.error} role="alert">{error}</p>}
    </div>
  );
}
