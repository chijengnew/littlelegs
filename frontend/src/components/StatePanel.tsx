import type { ReactNode } from "react";
import Mascot from "./art/Mascot";
import s from "./StatePanel.module.css";

export type StateTone = "empty" | "success" | "pending" | "notFound" | "permission" | "error";

const LIGHT: readonly StateTone[] = ["empty", "success"];

function ToneIcon({ tone }: { tone: StateTone }) {
  const common = {
    viewBox: "0 0 24 24",
    width: 28,
    height: 28,
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
    focusable: false,
  };
  if (tone === "permission") {
    return (
      <svg {...common}>
        <rect x="5" y="11" width="14" height="9" rx="2" />
        <path d="M8 11V8a4 4 0 0 1 8 0v3" />
      </svg>
    );
  }
  if (tone === "notFound") {
    return (
      <svg {...common}>
        <path d="M12 21s-7-6.5-7-11.5a7 7 0 0 1 14 0C19 14.5 12 21 12 21Z" />
        <path d="M10 8.5a2 2 0 1 1 2.7 1.9c-.5.2-.7.6-.7 1.1v.5" />
        <circle cx="12" cy="14.6" r=".6" fill="currentColor" />
      </svg>
    );
  }
  if (tone === "pending") {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7.5V12l3 2" />
      </svg>
    );
  }
  if (tone === "success") {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="9" />
        <path d="m8 12.5 2.8 2.8L16.5 9.5" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <path d="M12 3.5 2.8 19.5h18.4Z" />
      <path d="M12 10v4" />
      <circle cx="12" cy="16.8" r=".6" fill="currentColor" />
    </svg>
  );
}

export default function StatePanel({
  tone,
  title,
  description,
  actions,
  level = 2,
  inline = false,
  mascot = true,
  live,
}: {
  tone: StateTone;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  level?: 1 | 2;
  inline?: boolean;
  mascot?: boolean;
  live?: "status" | "alert";
}) {
  const Heading = level === 1 ? "h1" : "h2";
  const showMascot = mascot && LIGHT.includes(tone);
  return (
    <section className={inline ? s.inline : s.page} data-tone={tone} role={live}>
      {showMascot ? (
        <span className={s.mascot}>
          <Mascot />
        </span>
      ) : (
        <span className={s.icon}>
          <ToneIcon tone={tone} />
        </span>
      )}
      <Heading className={s.title}>{title}</Heading>
      {description && <div className={s.description}>{description}</div>}
      {actions && <div className={s.actions}>{actions}</div>}
    </section>
  );
}
