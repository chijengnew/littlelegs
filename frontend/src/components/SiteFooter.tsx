import Link from "next/link";
import { getTranslations } from "next-intl/server";
import s from "./SiteFooter.module.css";

export default async function SiteFooter() {
  const t = await getTranslations("app");
  return (
    <footer className={s.footer}>
      <div className={s.inner}>
        <p className={s.copy}>© LittleLegs</p>
        <nav className={s.nav} aria-label={t("footerNav")}>
          <ul className={s.links}>
            <li><Link href="/privacy">{t("privacy")}</Link></li>
            <li><Link href="/terms">{t("terms")}</Link></li>
            <li><Link href="/feedback?from=footer">{t("feedback")}</Link></li>
          </ul>
        </nav>
      </div>
    </footer>
  );
}
