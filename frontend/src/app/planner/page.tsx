import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Planner from "@/components/Planner";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("planner");
  return { title: t("pageTitle") };
}

export default function PlannerPage() {
  return <Planner />;
}
