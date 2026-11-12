"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import StatePanel from "../StatePanel";
import ui from "../ui.module.css";

export default function AccountDeleted() {
  const t = useTranslations();
  const accepted = useSearchParams().get("status") === "accepted";
  return (
    <StatePanel
      tone={accepted ? "pending" : "success"}
      level={1}
      live="status"
      mascot={false}
      title={t(accepted ? "deleteAccount.acceptedTitle" : "deleteAccount.doneTitle")}
      description={<p>{t(accepted ? "deleteAccount.accepted" : "deleteAccount.done")}</p>}
      actions={<Link className={ui.primary} href="/">{t("deleteAccount.home")}</Link>}
    />
  );
}
