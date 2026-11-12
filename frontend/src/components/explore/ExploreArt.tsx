import { useId, type ReactNode, type SVGProps } from "react";
import PlaceArt from "../art/PlaceArt";
import Mascot from "../art/Mascot";
import s from "./explore.module.css";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

export function StampIcon({ size = 18, ...rest }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      <path d="M9.5 3.5h5v3.2c0 1.2.6 2 1.6 2.6l.4.2c.9.5 1.5 1.5 1.5 2.5v.5h-12V12c0-1 .6-2 1.5-2.5l.4-.2c1-.6 1.6-1.4 1.6-2.6Z" fill="currentColor" fillOpacity="0.16" />
      <path d="M4.5 15.5h15" />
      <path d="M6.5 19.5h11" strokeDasharray="2 2.5" />
    </svg>
  );
}

function Rough({ id }: { id: string }) {
  return (
    <filter id={id} x="-10%" y="-10%" width="120%" height="120%">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="noise" />
      <feDisplacementMap in="SourceGraphic" in2="noise" scale="2.2" />
    </filter>
  );
}

export function Stamp({
  type,
  method,
  label,
  size = 104,
  className = "",
}: {
  type: string | null | undefined;
  method: "location" | "manual";
  label?: string;
  size?: number;
  className?: string;
}) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const top = `st-top-${uid}`;
  const bottom = `st-bottom-${uid}`;
  const rough = `st-rough-${uid}`;
  return (
    <span className={`${s.stamp} ${className}`} data-method={method} style={{ width: size, height: size }} aria-hidden="true">
      <svg viewBox="0 0 120 120" className={s.stampRing} focusable="false">
        <defs>
          <Rough id={rough} />
          <path id={top} d="M 22 60 A 38 38 0 0 1 98 60" />
          <path id={bottom} d="M 15 60 A 45 45 0 0 0 105 60" />
        </defs>
        <g filter={`url(#${rough})`}>
          <circle cx="60" cy="60" r="55" className={s.ringOuter} />
          <circle cx="60" cy="60" r="47" className={s.ringInner} />
          <text className={s.ringText}>
            <textPath href={`#${top}`} startOffset="50%" textAnchor="middle">LITTLELEGS</textPath>
          </text>
          {label && (
            <text className={s.ringText}>
              <textPath href={`#${bottom}`} startOffset="50%" textAnchor="middle">
                {label}
              </textPath>
            </text>
          )}
          <path d="M14 60h4M102 60h4" className={s.ringTick} />
        </g>
      </svg>
      <PlaceArt type={type} className={s.stampArt} />
    </span>
  );
}

function FootprintGlyph() {
  return (
    <svg viewBox="0 0 48 48" className={s.badgeGlyph} focusable="false" aria-hidden="true">
      <ellipse cx="18" cy="27" rx="6" ry="9" className={s.badgeInk} transform="rotate(-12 18 27)" />
      <circle cx="13" cy="15" r="2.2" className={s.badgeInk} />
      <circle cx="18" cy="13" r="2.4" className={s.badgeInk} />
      <circle cx="23" cy="15" r="2.2" className={s.badgeInk} />
      <ellipse cx="32" cy="33" rx="5.2" ry="7.6" className={s.badgeAccent} transform="rotate(10 32 33)" />
      <circle cx="28.5" cy="23" r="1.9" className={s.badgeAccent} />
      <circle cx="33" cy="21.6" r="2.1" className={s.badgeAccent} />
      <circle cx="37.2" cy="23.6" r="1.9" className={s.badgeAccent} />
    </svg>
  );
}

const BADGE_CONTENT: Record<string, () => ReactNode> = {
  first_stamp: () => <FootprintGlyph />,
  park_explorer: () => <PlaceArt type="park_playground" className={s.badgeArt} />,
  culture_scholar: () => <PlaceArt type="museum" className={s.badgeArt} />,
  little_explorer: () => (
    <span className={s.badgeMascot}>
      <Mascot size={40} />
    </span>
  ),
};

export function Badge({ code, unlocked, size = 88 }: { code: string; unlocked: boolean; size?: number }) {
  const content = BADGE_CONTENT[code] ?? BADGE_CONTENT.first_stamp;
  return (
    <span className={s.badge} data-locked={unlocked ? undefined : ""} style={{ width: size, height: size * 1.18 }} aria-hidden="true">
      <svg viewBox="0 0 100 118" className={s.badgeShape} focusable="false">
        <path d="M30 70 20 114l16-9 10 13 6-40Z" className={s.ribbonA} />
        <path d="M70 70 80 114l-16-9-10 13-6-40Z" className={s.ribbonB} />
        <path
          d="M50 4c5 0 7 4 12 5s9-2 13 1 3 8 6 12 8 5 9 10-3 8-3 13 4 9 2 14-7 5-10 9-2 9-6 12-9 0-14 2-7 5-12 5-7-4-12-5-9 2-13-1-3-8-6-12-8-5-9-10 3-8 3-13-4-9-2-14 7-5 10-9 2-9 6-12 9 0 14-2 7-5 12-5Z"
          className={s.medal}
        />
        <circle cx="50" cy="50" r="31" className={s.medalFace} />
      </svg>
      <span className={s.badgeCenter}>{content()}</span>
      {!unlocked && (
        <span className={s.badgeLock}>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" focusable="false" aria-hidden="true">
            <rect x="5" y="11" width="14" height="9" rx="2" />
            <path d="M8 11V8a4 4 0 0 1 8 0v3" />
          </svg>
        </span>
      )}
    </span>
  );
}
