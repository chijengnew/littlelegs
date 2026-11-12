import { useTranslations } from "next-intl";
import { dateLines, taipeiDay, type CheckIn } from "@/lib/stamping";
import { fullDate } from "../account/savedText";
import ui from "../ui.module.css";
import s from "./explore.module.css";

export function CheckInDates({ checkIn }: { checkIn: Pick<CheckIn, "verification_method" | "visited_at" | "verified_at"> }) {
  const t = useTranslations("explore.date");
  return (
    <dl className={s.dates}>
      {dateLines(checkIn).map((d) => (
        <div key={d.key}>
          <dt>{t(d.key)}</dt>
          <dd>{fullDate(taipeiDay(d.at))}</dd>
        </div>
      ))}
    </dl>
  );
}

export function MethodChip({ method }: { method: CheckIn["verification_method"] }) {
  const t = useTranslations("explore.method");
  return <span className={method === "location" ? ui.chipGreen : ui.chip}>{t(method)}</span>;
}
