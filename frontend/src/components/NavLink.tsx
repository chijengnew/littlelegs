import type { ReactNode } from "react";

export default function NavLink({
  href,
  className,
  label,
  children,
}: {
  href: string;
  className?: string;
  label?: string;
  children: ReactNode;
}) {
  return (
    <a href={href} className={className} aria-label={label} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}
