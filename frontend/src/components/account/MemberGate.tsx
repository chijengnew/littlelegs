"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { withNext } from "@/lib/authFlow";
import { useAuth } from "../AuthProvider";
import { SkeletonCard } from "../Skeleton";
import SignOutButton from "../auth/SignOutButton";
import ui from "../ui.module.css";
import StatePanel from "../StatePanel";

export default function MemberGate({ next, children }: { next: string; children: ReactNode }) {
  const t = useTranslations();
  const auth = useAuth();

  if (!auth.configured) {
    return <StatePanel tone="permission" inline live="status" title={t("auth.disabledFeature")} />;
  }
  if (!auth.booted) return <SkeletonCard lines={4} />;
  if (!auth.user) {
    return (
      <StatePanel
        tone="permission"
        inline
        title={t("auth.needLoginTitle")}
        description={<p>{t("auth.needLoginLead")}</p>}
        actions={
          <>
            <Link className={ui.primary} href={withNext("/login", next)}>{t("auth.toLogin")}</Link>
            <Link className={ui.secondary} href={withNext("/register", next)}>{t("auth.toRegister")}</Link>
          </>
        }
      />
    );
  }
  if (auth.error) {
    return (
      <StatePanel
        tone="error"
        inline
        live="alert"
        title={t("auth.verificationFailed")}
        description={
          <>
            <p>{auth.error.message}</p>
            <p>{t("auth.errorCode", { code: auth.error.code })}</p>
          </>
        }
        actions={
          <>
            <button type="button" className={ui.primary} onClick={auth.retry}>{t("auth.retryVerification")}</button>
            <SignOutButton />
          </>
        }
      />
    );
  }
  if (!auth.member) return <SkeletonCard lines={4} />;
  return <>{children}</>;
}
