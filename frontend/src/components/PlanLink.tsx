"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { usePlanner } from "./PlannerProvider";

export default function PlanLink({ className }: { className: string }) {
  const t = useTranslations("app");
  const { inProgress } = usePlanner();
  return (
    <Link href="/planner" className={className}>
      {t(inProgress ? "resumePlanning" : "startPlanning")}
    </Link>
  );
}
