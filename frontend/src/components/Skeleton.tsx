import s from "./Skeleton.module.css";

export function SkeletonLine({ width = "100%" }: { width?: string }) {
  return <span className={s.line} style={{ width }} aria-hidden="true" />;
}

export function SkeletonCard({ lines = 3, height }: { lines?: number; height?: number }) {
  return (
    <div className={s.card} style={height ? { minHeight: height } : undefined} aria-hidden="true">
      <span className={s.title} />
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className={s.line} style={{ width: `${90 - i * 15}%` }} />
      ))}
    </div>
  );
}

export function SkeletonList({ count = 4, lines = 3 }: { count?: number; lines?: number }) {
  return (
    <div className={s.fadeIn} aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <SkeletonCard key={i} lines={lines} />
      ))}
    </div>
  );
}

export const fadeIn = s.fadeIn;
export const appear = s.appear;
