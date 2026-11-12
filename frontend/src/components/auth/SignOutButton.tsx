"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { getFirebaseAuth } from "@/lib/firebaseClient";
import { LogoutIcon } from "../icons";
import ui from "../ui.module.css";

export default function SignOutButton({ to = "/", className = ui.secondary, icon = false }: { to?: string; className?: string; icon?: boolean }) {
  const t = useTranslations("auth");
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  async function signOut() {
    if (busy) return;
    setBusy(true);
    setError(false);
    try {
      const instance = await getFirebaseAuth();
      const { signOut: firebaseSignOut } = await import("firebase/auth");
      await firebaseSignOut(instance);
      router.push(to);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" className={className} onClick={signOut} disabled={busy} aria-busy={busy}>
        {icon && <LogoutIcon size={18} />}
        {t("logout")}
      </button>
      {error && <p className={ui.error} role="alert">{t("logoutFailed")}</p>}
    </>
  );
}
