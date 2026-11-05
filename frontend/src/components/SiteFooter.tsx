import Link from "next/link";
import { getTranslations } from "next-intl/server";
import s from "./SiteFooter.module.css";

export default async function SiteFooter() {
  const t = await getTranslations("app");
  return (
    <footer className={s.footer}>
      <p>{t("footerNote")}</p>
      <p className={s.links}>
        <Link href="/privacy">{t("privacy")}</Link>
        <span aria-hidden="true">·</span>
        <Link href="/terms">{t("terms")}</Link>
        <span aria-hidden="true">·</span>
        <Link href="/feedback?from=footer">{t("feedback")}</Link>
        <span aria-hidden="true">·</span>
        <span>© Littlelegs</span>
      </p>
    </footer>
  );
}
