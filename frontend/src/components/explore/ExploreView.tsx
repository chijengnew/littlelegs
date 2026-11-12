"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { withNext } from "@/lib/authFlow";
import { useAuth } from "../AuthProvider";
import MemberGate from "../account/MemberGate";
import { SkeletonCard } from "../Skeleton";
import { Badge, Stamp } from "./ExploreArt";
import Missions from "./Missions";
import Passport from "./Passport";
import auth from "../auth/auth.module.css";
import ui from "../ui.module.css";
import s from "./explore.module.css";

export type ExploreTab = "passport" | "missions";
const TABS: { key: ExploreTab; href: string; label: string }[] = [
  { key: "passport", href: "/explore/passport", label: "tabPassport" },
  { key: "missions", href: "/explore/missions", label: "tabMissions" },
];

export default function ExploreView({ tab }: { tab: ExploreTab }) {
  const t = useTranslations("explore");
  const session = useAuth();
  const guest = session.booted && !session.pending && !session.user;
  const next = `/explore/${tab}`;
  return (
    <div className={s.page}>
      <h1>{t("title")}</h1>
      <div className={s.body}>
        <nav className={auth.accountNav} aria-label={t("nav")}>
          {TABS.map((x) => (
            <Link key={x.key} href={x.href} scroll={false} className={auth.accountLink} aria-current={tab === x.key ? "page" : undefined}>
              {t(x.label)}
            </Link>
          ))}
        </nav>
        {!session.configured || guest ? (
          <GuestIntro next={next} enabled={session.configured} />
        ) : !session.booted || session.pending ? (
          <SkeletonCard lines={4} />
        ) : (
          <MemberGate next={next}>{tab === "passport" ? <Passport /> : <Missions />}</MemberGate>
        )}
      </div>
    </div>
  );
}

function GuestIntro({ next, enabled }: { next: string; enabled: boolean }) {
  const t = useTranslations();
  return (
    <section className={`${ui.card} ${s.intro}`} aria-labelledby="explore-intro">
      <h2 id="explore-intro">{t("explore.guest.title")}</h2>
      <p>{t("explore.guest.lead")}</p>
      <ol className={s.steps}>
        <li>{t("explore.guest.steps.visit")}</li>
        <li>{t("explore.guest.steps.check")}</li>
        <li>{t("explore.guest.steps.stamp")}</li>
        <li>{t("explore.guest.steps.badge")}</li>
      </ol>
      <figure className={s.demo} style={{ margin: 0 }}>
        <figcaption className={ui.chip}>{t("explore.sample")}</figcaption>
        <div className={s.demoRow} aria-hidden="true">
          <Stamp type="park_playground" method="location" label="2026.11.13" size={88} />
          <Stamp type="museum" method="manual" label="2026.11.14" size={88} />
          <Badge code="park_explorer" unlocked size={68} />
          <Badge code="little_explorer" unlocked={false} size={68} />
        </div>
      </figure>
      <p className={s.muted}>{t("explore.guest.note")}</p>
      {enabled ? (
        <div className={s.actions} style={{ justifyContent: "center" }}>
          <Link className={ui.primary} href={withNext("/login", next)}>{t("explore.guest.login")}</Link>
          <Link className={ui.secondary} href={withNext("/register", next)}>{t("explore.guest.register")}</Link>
        </div>
      ) : (
        <p className={s.muted}>{t("auth.disabledFeature")}</p>
      )}
    </section>
  );
}
