import a from "./art.module.css";

export function MascotShape() {
  return (
    <g>
      <path d="M2 -33 C3 -38 5 -42 9 -45" className={a.stem} />
      <path d="M8 -44 C10 -55 21 -61 31 -58 C29 -48 20 -42 8 -44 Z" className={a.leaf} />
      <path d="M5 -42 C1 -49 -6 -51 -11 -48 C-8 -43 -2 -40 5 -42 Z" className={a.leafDark} />
      <path d="M-15 22 C-21 22 -24 26 -21 28 C-17 30 -11 29 -9 26 Z" className={a.mascotFoot} />
      <path d="M9 25 C11 21 18 21 21 24 C23 27 19 30 13 29 C10 29 8 27 9 25 Z" className={a.mascotFoot} />
      <path d="M2 -34 C13 -27 25 -11 24 5 C23 19 13 28 -1 28 C-15 28 -25 18 -24 4 C-23 -11 -11 -27 2 -34 Z" className={a.mascotBody} />
      <path d="M-2 -26 C-11 -16 -17 -6 -17 6" className={a.mascotCrease} />
      <ellipse cx="-7" cy="2" rx="2.1" ry="2.8" className={a.ink} />
      <ellipse cx="8" cy="1" rx="2.1" ry="2.8" className={a.ink} />
      <path d="M-2 9 Q1 12 4 9" className={a.mascotMouth} />
    </g>
  );
}

export default function Mascot({ size = 96 }: { size?: number }) {
  return (
    <svg viewBox="-36 -64 72 96" width={size} height={(size * 96) / 72} className={a.svg} aria-hidden="true" focusable="false">
      <MascotShape />
    </svg>
  );
}
