import type { CSSProperties, ReactNode } from "react";
import s from "./PlaceArt.module.css";

const I = "var(--ink-800)";
const A = "var(--art-accent)";
const W = "var(--surface)";
const L = { stroke: I, strokeWidth: 2, strokeLinejoin: "round", strokeLinecap: "round" } as const;

const WHEEL: [number, number][] = [
  [37, 20],
  [30.5, 31.3],
  [17.5, 31.3],
  [11, 20],
  [17.5, 8.7],
  [30.5, 8.7],
];

const GLYPHS: Record<string, ReactNode> = {
  street: (
    <>
      <path d="M24 8v32M16 40h16" fill="none" {...L} />
      <path d="M10 12h20l5 4.5-5 4.5H10Z" fill={A} {...L} />
      <path d="M38 24H18l-5 4.5 5 4.5h20Z" fill={W} {...L} />
    </>
  ),
  indigenous: (
    <>
      <path d="M24 6 41 24 24 42 7 24Z" fill={A} {...L} />
      <path d="M24 14 34 24 24 34 14 24Z" fill={W} {...L} />
      <path d="M24 20 28 24 24 28 20 24Z" fill={I} />
    </>
  ),
  night_market: (
    <>
      <path d="M24 4v6M24 38v6" fill="none" {...L} />
      <ellipse cx="24" cy="24" rx="13" ry="13" fill={A} {...L} />
      <path d="M24 11c-6 4-6 22 0 26M24 11c6 4 6 22 0 26" fill="none" stroke={I} strokeWidth="1.5" />
      <rect x="16" y="8" width="16" height="4" rx="1.5" fill={I} />
      <rect x="16" y="36" width="16" height="4" rx="1.5" fill={I} />
    </>
  ),
  temple: (
    <>
      <path d="M5 18c7 0 12-3 19-9 7 6 12 9 19 9Z" fill={A} {...L} />
      <rect x="12" y="18" width="24" height="6" fill={W} {...L} />
      <path d="M8 28c6 0 11-1 16-4 5 3 10 4 16 4Z" fill={A} {...L} />
      <path d="M14 28v12M34 28v12M8 40h32" fill="none" {...L} />
      <rect x="20" y="31" width="8" height="9" fill={I} />
    </>
  ),
  industry_heritage: (
    <>
      {[0, 45, 90, 135, 180, 225, 270, 315].map((r) => (
        <rect key={r} x="20.5" y="5" width="7" height="9" rx="1.5" fill={A} {...L} transform={`rotate(${r} 24 24)`} />
      ))}
      <circle cx="24" cy="24" r="12.5" fill={A} {...L} />
      <circle cx="24" cy="24" r="4.5" fill={W} {...L} />
    </>
  ),
  old_street: (
    <>
      <rect x="10" y="21" width="28" height="19" fill={W} {...L} />
      <path d="M4 21c6 0 12-5 20-11 8 6 14 11 20 11Z" fill={A} {...L} />
      <rect x="20" y="28" width="8" height="12" fill={I} />
      <path d="M13 27h4M31 27h4" fill="none" {...L} />
    </>
  ),
  shop_cafe: (
    <>
      <path d="M16 5c-2 2 2 4 0 7M22 5c-2 2 2 4 0 7M28 5c-2 2 2 4 0 7" fill="none" {...L} />
      <path d="M9 17h24v10a10 10 0 0 1-10 10h-4A10 10 0 0 1 9 27Z" fill={A} {...L} />
      <path d="M33 20h3a4.5 4.5 0 0 1 0 9h-3" fill="none" {...L} />
      <path d="M7 41h28" fill="none" {...L} />
    </>
  ),
  zoo: (
    <>
      <ellipse cx="24" cy="31" rx="9" ry="7.5" fill={A} {...L} />
      <circle cx="13" cy="21" r="4" fill={I} />
      <circle cx="20" cy="14.5" r="4" fill={I} />
      <circle cx="28" cy="14.5" r="4" fill={I} />
      <circle cx="35" cy="21" r="4" fill={I} />
    </>
  ),
  tourism_factory: (
    <>
      <path d="M35 6c2-2 4-2 5 0" fill="none" {...L} />
      <path d="M6 40V23l9 5v-5l9 5v-5l9 5V10h7v30Z" fill={A} {...L} />
      <rect x="10" y="32" width="5" height="4" rx="1" fill={W} />
      <rect x="19" y="32" width="5" height="4" rx="1" fill={W} />
      <rect x="28" y="32" width="5" height="4" rx="1" fill={W} />
    </>
  ),
  heritage: (
    <>
      <path d="M7 40V15h6v5h5v-5h4v5h4v-5h4v5h5v-5h6v25Z" fill={A} {...L} />
      <path d="M19 40v-7a5 5 0 0 1 10 0v7Z" fill={I} />
    </>
  ),
  hakka: (
    <>
      {[0, 72, 144, 216, 288].map((r) => (
        <ellipse key={r} cx="24" cy="13.5" rx="6" ry="8.5" fill={W} {...L} transform={`rotate(${r} 24 24)`} />
      ))}
      <circle cx="24" cy="24" r="5" fill={A} {...L} />
    </>
  ),
  farm: (
    <>
      <path d="M7 40V20l17-11 17 11v20Z" fill={A} {...L} />
      <rect x="17" y="25" width="14" height="15" fill={W} {...L} />
      <path d="m17 25 14 15M31 25 17 40M21 17h6" fill="none" {...L} />
    </>
  ),
  trail: (
    <>
      <circle cx="37" cy="11" r="4" fill={W} {...L} />
      <path d="M4 40 18 16l8 10 5-7 13 21Z" fill={A} {...L} />
      <path d="M14 40c2-4 8-5 10-9s-2-6 2-9" fill="none" stroke={W} strokeWidth="2.5" strokeLinecap="round" strokeDasharray="2 3.5" />
    </>
  ),
  env_edu: (
    <>
      <path d="M10 40h28M24 40V23" fill="none" {...L} />
      <path d="M24 27c0-8-6-12-14-12 0 8 6 12 14 12Z" fill={A} {...L} />
      <path d="M24 23c0-7 5-12 13-12 0 7-5 12-13 12Z" fill={A} {...L} />
    </>
  ),
  bike_path: (
    <>
      <circle cx="13" cy="31" r="8" fill="none" {...L} />
      <circle cx="35" cy="31" r="8" fill="none" {...L} />
      <path d="M13 31 20 19l3 12Zm10 0 8-12H20m11 0 4 12m-4-12-1-4h4M17 16h6" fill="none" stroke={A} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  park_playground: (
    <>
      <path d="M6 40h36M11 40V12M19 40V12M11 19h8M11 26h8M11 33h8" fill="none" {...L} />
      <path d="M19 12h4c4 0 6 3 8 9s4 13 10 15" fill="none" stroke={I} strokeWidth="7" strokeLinecap="round" />
      <path d="M19 12h4c4 0 6 3 8 9s4 13 10 15" fill="none" stroke={A} strokeWidth="4" strokeLinecap="round" />
    </>
  ),
  nature: (
    <>
      <circle cx="35" cy="13" r="5" fill={W} {...L} />
      <path d="M3 40 17 17l8 11 6-8 14 20Z" fill={A} {...L} />
    </>
  ),
  nature_center: (
    <>
      <path d="M24 22c-3-8-9-12-14-11-4 1-4 7 0 11 3 3 9 3 14 0Z" fill={A} {...L} />
      <path d="M24 22c3-8 9-12 14-11 4 1 4 7 0 11-3 3-9 3-14 0Z" fill={A} {...L} />
      <path d="M24 24c-2 5-6 9-10 9-3 0-3-4-1-6 3-2 7-3 11-3Z" fill={W} {...L} />
      <path d="M24 24c2 5 6 9 10 9 3 0 3-4 1-6-3-2-7-3-11-3Z" fill={W} {...L} />
      <path d="M24 14v20M24 14l-3-4M24 14l3-4" fill="none" {...L} />
    </>
  ),
  hot_spring: (
    <>
      <path d="M16 26c-3-3 3-6 0-9s3-6 0-9M24 26c-3-3 3-6 0-9s3-6 0-9M32 26c-3-3 3-6 0-9s3-6 0-9" fill="none" {...L} />
      <ellipse cx="24" cy="34" rx="16" ry="6" fill={A} {...L} />
    </>
  ),
  beach: (
    <>
      <path d="M6 40c8-4 28-4 36 0M24 20l6 18" fill="none" {...L} />
      <path d="M8 20a16 12 0 0 1 32 0Z" fill={A} {...L} />
      <path d="M18 20c0-6 2-10 6-12M30 20c0-6-2-10-6-12" fill="none" stroke={I} strokeWidth="1.5" />
    </>
  ),
  scenic_ride: (
    <>
      <path d="M4 9 44 17M24 13v6" fill="none" {...L} />
      <rect x="12" y="19" width="24" height="20" rx="4" fill={A} {...L} />
      <rect x="16" y="23" width="7" height="6" rx="1" fill={W} />
      <rect x="25" y="23" width="7" height="6" rx="1" fill={W} />
    </>
  ),
  aquarium: (
    <>
      <path d="M6 24c5-7 11-10 17-10 6 0 10 3 13 6l6-5v18l-6-5c-3 3-7 6-13 6-6 0-12-3-17-10Z" fill={A} {...L} />
      <circle cx="15" cy="22" r="2" fill={I} />
      <path d="M22 19c2 3 2 7 0 10" fill="none" {...L} />
    </>
  ),
  waterfront: (
    <>
      <path d="M24 6v26" fill="none" {...L} />
      <path d="M24 8 38 28H24Z" fill={A} {...L} />
      <path d="M22 12 12 28h10Z" fill={W} {...L} />
      <path d="M8 32h32l-5 7H13Z" fill={I} />
      <path d="M5 43c4-3 8-3 12 0s8 3 12 0 8-3 12 0" fill="none" {...L} />
    </>
  ),
  station: (
    <>
      <path d="m16 35-4 6M32 35l4 6M10 41h28" fill="none" {...L} />
      <rect x="12" y="7" width="24" height="28" rx="6" fill={A} {...L} />
      <rect x="16" y="12" width="16" height="9" rx="2" fill={W} {...L} />
      <circle cx="18" cy="28" r="2" fill={I} />
      <circle cx="30" cy="28" r="2" fill={I} />
    </>
  ),
  visitor_center: (
    <>
      <circle cx="24" cy="24" r="16" fill={A} {...L} />
      <circle cx="24" cy="16" r="2.5" fill={W} />
      <path d="M24 22v12" fill="none" stroke={W} strokeWidth="4" strokeLinecap="round" />
    </>
  ),
  museum: (
    <>
      <path d="M7 18 24 8l17 10Z" fill={A} {...L} />
      <path d="M12 21v13M20 21v13M28 21v13M36 21v13" fill="none" stroke={I} strokeWidth="3" strokeLinecap="round" />
      <rect x="7" y="36" width="34" height="4" rx="2" fill={I} />
    </>
  ),
  landmark: (
    <>
      <path d="M14 40V30h3v-8h3v-8h2V6h4v8h2v8h3v8h3v10Z" fill={A} {...L} />
      <path d="M10 40h28" fill="none" {...L} />
    </>
  ),
  library: (
    <>
      <path d="M24 15c-5-4-11-5-17-4v25c6-1 12 0 17 4 5-4 11-5 17-4V11c-6-1-12 0-17 4Z" fill={A} {...L} />
      <path d="M24 15v25" fill="none" {...L} />
      <path d="M11 18c3 0 6 .5 9 2M11 24c3 0 6 .5 9 2M28 20c3-1.5 6-2 9-2M28 26c3-1.5 6-2 9-2" fill="none" stroke={W} strokeWidth="2" strokeLinecap="round" />
    </>
  ),
  campus: (
    <>
      <path d="M12 22v9c0 3 5 6 12 6s12-3 12-6v-9" fill={W} {...L} />
      <path d="M4 18 24 9l20 9-20 9Z" fill={A} {...L} />
      <path d="M40 20v10" fill="none" {...L} />
      <circle cx="40" cy="32" r="2" fill={I} />
    </>
  ),
  public_art: (
    <>
      <rect x="12" y="34" width="24" height="6" rx="1.5" fill={I} />
      <path d="M17 34 24 18l7 16Z" fill={A} {...L} />
      <circle cx="24" cy="12" r="6" fill={W} {...L} />
    </>
  ),
  diy_workshop: (
    <>
      <path d="M24 8C14 8 6 15 6 23.5 6 32 13 39 20 39c3 0 4-2 3-4.5s.5-4.5 3.5-4.5H32c6 0 10-3.5 10-8.5C42 14 34 8 24 8Z" fill={A} {...L} />
      <circle cx="16" cy="21" r="3" fill={W} {...L} />
      <circle cx="24" cy="15" r="3" fill={I} />
      <circle cx="32.5" cy="18.5" r="3" fill={W} {...L} />
    </>
  ),
  arts_venue: (
    <>
      <path d="M10 10h28v12c0 9-6 16-14 16s-14-7-14-16Z" fill={A} {...L} />
      <path d="M15 19c1.5-2 4.5-2 6 0M27 19c1.5-2 4.5-2 6 0" fill="none" {...L} />
      <path d="M17 27c3 4 11 4 14 0Z" fill={I} {...L} />
    </>
  ),
  amusement_park: (
    <>
      <path d="M16 41 24 21l8 20M12 41h24" fill="none" {...L} />
      <circle cx="24" cy="20" r="13" fill={W} {...L} />
      <path d="M24 7v26M11 20h26M14.8 10.8l18.4 18.4M33.2 10.8 14.8 29.2" stroke={I} strokeWidth="1.5" />
      {WHEEL.map(([x, y]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r="3" fill={A} {...L} />
      ))}
    </>
  ),
  sports: (
    <>
      <circle cx="24" cy="23" r="14" fill={A} {...L} />
      <path d="M13.5 13.5c6 5 6 14 0 19M34.5 13.5c-6 5-6 14 0 19" fill="none" stroke={W} strokeWidth="2.5" strokeLinecap="round" />
    </>
  ),
  shopping: (
    <>
      <path d="M10 16h28l-2 24H12Z" fill={A} {...L} />
      <path d="M18 20v-6a6 6 0 0 1 12 0v6" fill="none" {...L} />
    </>
  ),
  community: (
    <>
      <path d="M5 40V25l9-8 9 8v15Z" fill={W} {...L} />
      <rect x="11" y="31" width="6" height="9" fill={I} />
      <path d="M21 40V21l11-10 11 10v19Z" fill={A} {...L} />
      <rect x="29" y="30" width="6" height="10" fill={I} />
    </>
  ),
  parent_child_center: (
    <>
      <path d="M8 21 24 8l16 13v19H8Z" fill={A} {...L} />
      <path d="M24 34s-7.5-4.6-7.5-9.4a3.9 3.9 0 0 1 7.5-1.3 3.9 3.9 0 0 1 7.5 1.3c0 4.8-7.5 9.4-7.5 9.4Z" fill={W} {...L} />
    </>
  ),
  other: (
    <>
      <path d="M24 41s-11-11-11-20a11 11 0 0 1 22 0c0 9-11 20-11 20Z" fill={A} {...L} />
      <circle cx="24" cy="21" r="4" fill={W} {...L} />
    </>
  ),
};

export const TYPE_ORDER = Object.keys(GLYPHS).filter((k) => k !== "other");

function tone(type: string): CSSProperties | undefined {
  const i = TYPE_ORDER.indexOf(type);
  if (i < 0) return undefined;
  return { "--h": 25 + (i * 360) / TYPE_ORDER.length, "--l": i % 2 ? 0.925 : 0.955 } as CSSProperties;
}

export default function PlaceArt({ type, className = "" }: { type: string | null | undefined; className?: string }) {
  const key = type && GLYPHS[type] ? type : "other";
  const style = tone(key);
  return (
    <span className={`${s.tile} ${className}`} style={style} data-tone={style ? "" : undefined} aria-hidden="true">
      <svg viewBox="0 0 48 48" className={s.svg} focusable="false">
        {GLYPHS[key]}
      </svg>
    </span>
  );
}
