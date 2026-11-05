"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { safeNext, withNext } from "@/lib/authFlow";
import { useAuth } from "./AuthProvider";
import ui from "./ui.module.css";
import s from "./auth/auth.module.css";

export default function AccountNav() {
  const t = useTranslations();
  const auth = useAuth();
  const next = safeNext(usePathname());

  if (!auth.booted || auth.pending) {
    return (
      <>
        <span className="visually-hidden" role="status">{t("auth.verifying")}</span>
        <span className={ui.soft} style={{ visibility: "hidden" }} aria-hidden="true">{t("auth.member")}</span>
      </>
    );
  }
  if (auth.member) {
    return (
      <>
        <span className={s.status} role="status">{t("auth.verified")}</span>
        <Link className={ui.soft} href="/account">{t("auth.member")}</Link>
      </>
    );
  }
  if (auth.unverified) return <Link className={ui.soft} href={withNext("/verify-email", next)}>{t("auth.verifyEmailNav")}</Link>;
  if (auth.user) {
    return (
      <>
        {auth.error && <span className={s.status} role="status">{t("auth.verificationFailed")}</span>}
        <Link className={ui.soft} href="/account">{t("auth.account")}</Link>
      </>
    );
  }
  return <Link className={ui.soft} href={withNext("/login", next)}>{t("app.login")}</Link>;
}
