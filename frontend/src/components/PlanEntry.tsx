"use client";

import { usePathname } from "next/navigation";
import PlanLink from "./PlanLink";
import ui from "./ui.module.css";
import s from "./SiteHeader.module.css";

export default function PlanEntry() {
  if (usePathname() === "/planner") return null;
  return <PlanLink className={`${ui.primary} ${s.planEntry}`} />;
}
