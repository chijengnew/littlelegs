"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import StatePanel from "@/components/StatePanel";
import ui from "@/components/ui.module.css";

export default function ErrorPage({ error, retry }: { error: unknown; retry: () => void }) {
  const t = useTranslations();
  const digest = error instanceof Error && "digest" in error && typeof error.digest === "string" ? error.digest : null;
  return (
    <StatePanel
      tone="error"
      level={1}
      live="alert"
      title={t("state.errorTitle")}
      description={
        <>
          <p>{t("state.errorBody")}</p>
          {digest && <p>{t("state.errorCode", { code: digest })}</p>}
        </>
      }
      actions={
        <>
          <button type="button" className={ui.primary} onClick={() => retry()}>{t("state.retry")}</button>
          <Link className={ui.secondary} href="/">{t("state.home")}</Link>
        </>
      }
    />
  );
}
