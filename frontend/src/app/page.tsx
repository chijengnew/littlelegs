import { getTranslations } from "next-intl/server";
import { NavigationArt, PackingArt } from "@/components/art/FeatureArt";
import { HeroWideScene } from "@/components/art/HeroScene";
import Mascot from "@/components/art/Mascot";
import PlanLink from "@/components/PlanLink";
import PlaceArt from "@/components/art/PlaceArt";
import { ArrowDownIcon, CalendarIcon, CarIcon, CheckIcon, FlagIcon, MealIcon, MoonIcon, PinIcon, RouteIcon } from "@/components/icons";
import ui from "@/components/ui.module.css";
import s from "./home.module.css";

const STEPS = [
  { key: "conditions", Icon: CalendarIcon },
  { key: "candidates", Icon: PinIcon },
  { key: "itinerary", Icon: RouteIcon },
] as const;

type PreviewRow =
  | { kind: "move"; time: string; key: "move1" | "move2" | "move3" }
  | { kind: "stop"; time: string; key: "stop1" | "stop2"; n: number; type: string }
  | { kind: "meal" | "nap" | "arrive"; time: string; key: "lunch" | "nap" | "arrive" };

const PREVIEW: PreviewRow[] = [
  { kind: "move", time: "09:00", key: "move1" },
  { kind: "stop", time: "09:25", key: "stop1", n: 1, type: "zoo" },
  { kind: "move", time: "10:55", key: "move2" },
  { kind: "meal", time: "11:15", key: "lunch" },
  { kind: "nap", time: "12:15", key: "nap" },
  { kind: "stop", time: "13:30", key: "stop2", n: 2, type: "museum" },
  { kind: "move", time: "14:15", key: "move3" },
  { kind: "arrive", time: "14:45", key: "arrive" },
];

const MARK = { move: <CarIcon size={14} />, meal: <MealIcon size={14} />, nap: <MoonIcon size={14} />, arrive: <FlagIcon size={14} /> };

export default async function Home() {
  const t = await getTranslations("home");
  const keep = (c: React.ReactNode) => <span className={s.keep}>{c}</span>;
  return (
    <div className={s.page}>
      <section className={s.hero} aria-labelledby="home-title">
        <div className={s.heroInner}>
          <div className={s.heroCopy}>
            <h1 id="home-title" className={s.heroTitle}>
              <span>{t("titleLine1")}</span>
              <span className={s.accent}>{t("titleLine2")}</span>
            </h1>
            <p className={s.heroSub}>{t("subtitle")}</p>
            <div className={s.heroActions}>
              <PlanLink className={`${ui.primary} ${ui.large} ${s.cta} ${s.heroCta}`} />
              <a href="#how" className={s.textLink}>
                {t("howLink")}
                <ArrowDownIcon size={18} />
              </a>
            </div>
          </div>
        </div>
        <HeroWideScene className={s.heroArt} />
      </section>

      <section id="how" className={s.band} aria-labelledby="how-title">
        <div className={s.inner}>
          <h2 id="how-title" className={s.sectionTitle}>{t("howTitle")}</h2>
          <ol className={s.steps}>
            {STEPS.map(({ key, Icon }, i) => (
              <li key={key} className={s.step}>
                <div className={s.stepTop}>
                  <span className={`${s.stepNum} ${s[`num_${key}`]}`} aria-hidden="true">{i + 1}</span>
                  <Icon className={s.stepIcon} />
                </div>
                <h3 className={s.stepTitle}>{t(`steps.${key}.title`)}</h3>
                <p className={s.stepText}>{t(`steps.${key}.text`)}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className={s.preview} aria-labelledby="preview-title">
        <h2 id="preview-title" className={`${s.sectionTitle} ${s.previewTitle}`}>
          {t.rich("previewTitle", { keep })}
        </h2>
        <ul className={s.features}>
          <li className={s.feature}>
            <NavigationArt />
            <span className={s.featureText}>{t.rich("previewFeatures.nav", { keep })}</span>
          </li>
          <li className={s.feature}>
            <PackingArt />
            <span className={s.featureText}>{t.rich("previewFeatures.packing", { keep })}</span>
          </li>
        </ul>
        <figure className={s.previewCard}>
          <figcaption className={s.previewCaption}>
            <span className={s.sample}>{t("previewSample")}</span>
            <span className={s.previewMeta}>{t.rich("previewMeta", { keep })}</span>
            <span className={ui.chipGreen}><CheckIcon size={14} />{t("previewFeasible")}</span>
          </figcaption>
          <p className={s.previewHeading}>{t("previewTimeline")}</p>
          <ol className={s.timeline}>
            {PREVIEW.map((x) => (
              <li key={x.key} className={`${s.tlItem} ${s[`tl_${x.kind}`]}`}>
                <span className={s.tlTime}>{x.time}</span>
                <span className={s.tlDot} aria-hidden="true">
                  {x.kind === "stop" ? x.n : MARK[x.kind]}
                </span>
                <span className={s.tlBody}>
                  {x.kind === "stop" ? (
                    <span className={s.tlPlace}>
                      <PlaceArt type={x.type} className={s.tlArt} />
                      <span className={s.tlTitle}>{t(`previewItems.${x.key}`)}</span>
                    </span>
                  ) : (
                    <span className={s.tlTitle}>{t.rich(`previewItems.${x.key}`, { keep })}</span>
                  )}
                  {(x.kind === "move" || x.kind === "stop") && <span className={s.tlMeta}>{t(`previewItems.${x.key}Meta`)}</span>}
                </span>
              </li>
            ))}
          </ol>
        </figure>
      </section>

      <section className={s.closing} aria-labelledby="closing-title">
        <div className={s.closingInner}>
          <span className={s.closingMascot}>
            <Mascot />
          </span>
          <h2 id="closing-title" className={s.sectionTitle}>{t("closingTitle")}</h2>
          <p className={s.closingText}>{t("closingText")}</p>
          <PlanLink className={`${ui.primary} ${ui.large} ${s.cta}`} />
        </div>
      </section>
    </div>
  );
}
