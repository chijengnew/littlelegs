import Link from "next/link";
import { useTranslations } from "next-intl";
import { StampIcon } from "./ExploreArt";
import s from "./explore.module.css";

export type StampFrom = "plan" | "history" | "favorites" | "passport";

export const stampHref = (placeId: string, from: StampFrom) => `/places/${placeId}?from=${from}#stamp`;

export default function StampLink({
  placeId,
  name,
  from,
  className = s.pill,
}: {
  placeId: string;
  name: string;
  from: StampFrom;
  className?: string;
}) {
  const t = useTranslations("explore.link");
  return (
    <Link className={className} href={stampHref(placeId, from)} aria-label={t("stampLabel", { name })}>
      <StampIcon size={14} />
      {t("stamp")}
    </Link>
  );
}
