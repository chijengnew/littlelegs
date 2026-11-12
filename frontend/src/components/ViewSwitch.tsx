"use client";

import type { ReactNode } from "react";
import s from "./ViewSwitch.module.css";

type Option<T extends string> = { value: T; label: string; icon?: ReactNode };

export default function ViewSwitch<T extends string>({
  label,
  value,
  options,
  onChange,
  className = "",
}: {
  className?: string;
  label: string;
  value: T;
  options: Option<T>[];
  onChange: (value: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className={`${s.switch} ${className}`}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          className={s.option}
          aria-pressed={o.value === value}
          onClick={() => onChange(o.value)}
        >
          {o.icon}
          {o.label}
        </button>
      ))}
    </div>
  );
}
