import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import HeroScene from "../art/HeroScene";
import s from "./auth.module.css";

export default function AuthShell({ children }: { children: ReactNode }) {
  const t = useTranslations("authShell");
  return (
    <div className={s.shell}>
      <div className={s.panel}>{children}</div>
      <aside className={s.brand} aria-labelledby="auth-brand-title">
        <div className={s.brandArt}>
          <HeroScene />
        </div>
        <div className={s.brandText}>
          <p className={s.brandEyebrow}>{t("eyebrow")}</p>
          <h2 className={s.brandTitle} id="auth-brand-title">
            {t("title")}
          </h2>
          <ul className={s.benefits}>
            <li>{t("history")}</li>
            <li>{t("favorites")}</li>
            <li>{t("map")}</li>
          </ul>
        </div>
      </aside>
    </div>
  );
}
