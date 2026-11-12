import Link from "next/link";
import { useTranslations } from "next-intl";
import StatePanel from "@/components/StatePanel";
import ui from "@/components/ui.module.css";

export default function NotFound() {
  const t = useTranslations();
  return (
    <StatePanel
      tone="notFound"
      level={1}
      title={t("state.notFoundTitle")}
      description={<p>{t("state.notFoundBody")}</p>}
      actions={
        <>
          <Link className={ui.primary} href="/">{t("state.home")}</Link>
          <Link className={ui.secondary} href="/planner">{t("app.startPlanning")}</Link>
        </>
      }
    />
  );
}
