import type { ReactNode } from "react";
import Link from "next/link";
import s from "./auth.module.css";

export const legalLinks = {
  terms: (chunks: ReactNode) => (
    <span className={s.nowrap}>
      《<Link href="/terms">{chunks}</Link>》
    </span>
  ),
  privacy: (chunks: ReactNode) => (
    <span className={s.nowrap}>
      《<Link href="/privacy">{chunks}</Link>》
    </span>
  ),
};
