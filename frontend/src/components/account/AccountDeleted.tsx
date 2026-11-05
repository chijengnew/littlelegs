"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import ui from "../ui.module.css";
import a from "../auth/auth.module.css";

export default function AccountDeleted() {
  const t = useTranslations();
  const accepted = useSearchParams().get("status") === "accepted";
  return (
    <div className={a.wrap}>
      <section className={ui.card}>
        <h1 className={a.title}>{t("deleteAccount.doneTitle")}</h1>
        <p className={ui.bannerOk} role="status">{t(accepted ? "deleteAccount.accepted" : "deleteAccount.done")}</p>
        <div className={a.actions} style={{ marginTop: 16 }}>
          <Link className={ui.primary} href="/">{t("deleteAccount.home")}</Link>
        </div>
      </section>
    </div>
  );
}
