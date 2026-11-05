import { Suspense } from "react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import AccountNav from "./AccountNav";
import ui from "./ui.module.css";
import s from "./SiteHeader.module.css";

export default async function SiteHeader() {
  const t = await getTranslations("app");
  return (
    <header className={s.header}>
      <div className={s.inner}>
        <Link href="/" className={s.brand} aria-label={t("name")}>
          <span className={s.logo} aria-hidden="true">
            <svg viewBox="0 0 32 32" width="32" height="32">
              <circle cx="16" cy="16" r="16" fill="#1877f2" />
              <circle cx="11.5" cy="20" r="3.2" fill="#fff" />
              <circle cx="20.5" cy="20" r="3.2" fill="#fff" />
              <path d="M11.5 17V10.5M20.5 17V12" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
            </svg>
          </span>
          <span className={s.word}>littlelegs</span>
        </Link>
        <nav className={s.actions}>
          <Suspense fallback={<Link className={ui.soft} href="/login">{t("login")}</Link>}>
            <AccountNav />
          </Suspense>
        </nav>
      </div>
    </header>
  );
}
