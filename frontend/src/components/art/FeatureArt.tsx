import s from "./FeatureArt.module.css";

const INK = "var(--ink-800)";

function Frame({ tone, children }: { tone: "blue" | "sun"; children: React.ReactNode }) {
  return (
    <span className={`${s.tile} ${s[tone]}`} aria-hidden="true">
      <svg viewBox="0 0 64 64" className={s.svg} focusable="false">
        {children}
      </svg>
    </span>
  );
}

export function NavigationArt() {
  return (
    <Frame tone="blue">
      <path d="M7 15 21 10l22 6 14-5v38l-14 5-22-6-14 5Z" fill="var(--surface)" stroke={INK} strokeWidth="2" strokeLinejoin="round" />
      <path d="M21 10v38l22 6V16Z" fill="var(--paper-100)" stroke={INK} strokeWidth="2" strokeLinejoin="round" />
      <path d="M15 46c6-2 9-8 15-10s10 1 14-6" fill="none" stroke="var(--orange-500)" strokeWidth="3" strokeLinecap="round" strokeDasharray="0.1 5.5" />
      <circle cx="14" cy="46" r="4" fill="var(--blue-500)" stroke={INK} strokeWidth="2" />
      <path d="M46 30s-8-7.5-8-13.5a8 8 0 0 1 16 0c0 6-8 13.5-8 13.5Z" fill="var(--orange-500)" stroke={INK} strokeWidth="2" strokeLinejoin="round" />
      <circle cx="46" cy="16.5" r="3" fill="var(--surface)" stroke={INK} strokeWidth="1.75" />
    </Frame>
  );
}

export function PackingArt() {
  return (
    <Frame tone="sun">
      <rect x="10" y="11" width="34" height="45" rx="5" fill="var(--surface)" stroke={INK} strokeWidth="2" />
      <rect x="19" y="7" width="16" height="8" rx="2.5" fill="var(--sun-400)" stroke={INK} strokeWidth="2" />
      <rect x="16" y="22" width="7" height="7" rx="2" fill="var(--sage-500)" stroke={INK} strokeWidth="1.75" />
      <path d="m17.6 25.6 1.6 1.6 2.8-3.4" fill="none" stroke="var(--surface)" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="27" y="24" width="11" height="3" rx="1.5" fill="var(--paper-200)" />
      <rect x="16" y="34" width="7" height="7" rx="2" fill="var(--sage-500)" stroke={INK} strokeWidth="1.75" />
      <path d="m17.6 37.6 1.6 1.6 2.8-3.4" fill="none" stroke="var(--surface)" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="27" y="36" width="11" height="3" rx="1.5" fill="var(--paper-200)" />
      <rect x="16" y="46" width="7" height="7" rx="2" fill="var(--surface)" stroke={INK} strokeWidth="1.75" />
      <rect x="27" y="48" width="9" height="3" rx="1.5" fill={INK} />
      <rect x="44" y="36" width="12" height="21" rx="4" fill="var(--blue-500)" stroke={INK} strokeWidth="2" />
      <rect x="46.5" y="31" width="7" height="6" rx="1.5" fill={INK} />
      <path d="M44.5 45h11" stroke="var(--surface)" strokeWidth="2" opacity="0.6" />
    </Frame>
  );
}
