import { Suspense } from "react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import AccountMenu from "./AccountMenu";
import PlanEntry from "./PlanEntry";
import { BrandLogo } from "./icons";
import s from "./SiteHeader.module.css";

export default async function SiteHeader() {
  const t = await getTranslations("app");
  return (
    <header className={s.header}>
      <div className={s.inner}>
        <Link href="/" className={s.brand} aria-label={t("name")}>
          <BrandLogo height={24} />
          <span className={s.word} aria-hidden="true">LittleLegs</span>
        </Link>
        <nav className={s.actions} aria-label={t("accountNav")}>
          <Suspense fallback={null}>
            <PlanEntry />
          </Suspense>
          <Suspense fallback={<span className={s.placeholder} aria-hidden="true" />}>
            <AccountMenu />
          </Suspense>
        </nav>
      </div>
    </header>
  );
}
