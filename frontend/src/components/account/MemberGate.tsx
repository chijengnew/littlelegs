"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { withNext } from "@/lib/authFlow";
import { useAuth } from "../AuthProvider";
import { SkeletonCard } from "../Skeleton";
import SignOutButton from "../auth/SignOutButton";
import ui from "../ui.module.css";
import s from "../auth/auth.module.css";

export default function MemberGate({ next, children }: { next: string; children: ReactNode }) {
  const t = useTranslations();
  const auth = useAuth();

  if (!auth.configured) return <p className={ui.bannerWarn} role="status">{t("auth.disabledFeature")}</p>;
  if (!auth.booted) return <SkeletonCard lines={4} />;
  if (!auth.user) {
    return (
      <p className={s.lead}>
        {t("auth.needLogin")} <Link href={withNext("/login", next)}>{t("auth.toLogin")}</Link>
      </p>
    );
  }
  if (auth.error) {
    return (
      <div className={ui.bannerError} role="alert">
        <div>
          {auth.error.message}
          <p className={ui.hint}>{t("auth.errorCode", { code: auth.error.code })}</p>
          <div className={s.actions}>
            <button type="button" className={ui.soft} onClick={auth.retry}>{t("auth.retryVerification")}</button>
            <SignOutButton />
          </div>
        </div>
      </div>
    );
  }
  if (!auth.member) return <SkeletonCard lines={4} />;
  return <>{children}</>;
}
