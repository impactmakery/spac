"use client";

import { useState } from "react";

export interface BarDatum {
  label: string;
  value: number;
}

/** Horizontal bars: rounded data-ends anchored to the baseline, 2px gap between
 *  bars, values direct-labelled (no separate legend for one measure). */
export function BarChart({
  data,
  color = "var(--chart-1)",
  label,
}: {
  data: BarDatum[];
  color?: string;
  label: string;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const max = Math.max(1, ...data.map((d) => d.value));

  if (data.length === 0) {
    return <div className="h-32 rounded-lg bg-muted/50" aria-label={label} />;
  }

  return (
    <ul className="space-y-2.5" aria-label={label}>
      {data.map((d) => (
        <li
          key={d.label}
          className="grid grid-cols-[minmax(6rem,9rem)_1fr_auto] items-center gap-3"
          onMouseEnter={() => setHover(d.label)}
          onMouseLeave={() => setHover(null)}
        >
          <span className="truncate text-sm text-foreground" title={d.label}>
            {d.label}
          </span>
          <span className="h-3 rounded-full bg-muted">
            <span
              className="block h-3 rounded-full transition-[width]"
              style={{
                width: `${Math.max(2, (d.value / max) * 100)}%`,
                backgroundColor: color,
                opacity: hover && hover !== d.label ? 0.55 : 1,
              }}
            />
          </span>
          <span className="text-sm font-semibold tabular-nums text-foreground">
            {d.value}
          </span>
        </li>
      ))}
    </ul>
  );
}
