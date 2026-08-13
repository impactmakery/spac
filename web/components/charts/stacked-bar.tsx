"use client";

import { useState } from "react";

export interface StackSeries {
  key: string;
  label: string;
  color: string;
}

export interface StackDatum {
  label: string;
  values: Record<string, number>;
}

/**
 * Horizontal stacked bars: what each row's total is made of.
 *
 * Horizontal because the row labels are municipality names in Hebrew — long,
 * and unreadable rotated under a column. Stacked rather than a pie because
 * there are more rows than a pie can carry and most of them are near zero; a
 * pie of mostly-empty slices says less than the numbers alone.
 *
 * Segments carry a 2px surface gap so adjacent fills stay distinct without a
 * border, and the legend is always present — with three series, identity must
 * never rest on colour alone.
 */
export function StackedBar({
  data,
  series,
  label,
  emptyLabel,
}: {
  data: StackDatum[];
  series: StackSeries[];
  label: string;
  emptyLabel: string;
}) {
  const [hover, setHover] = useState<string | null>(null);

  const totals = data.map((d) => series.reduce((sum, s) => sum + (d.values[s.key] ?? 0), 0));
  const max = Math.max(1, ...totals);
  const anything = totals.some((t) => t > 0);

  if (!anything) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground" aria-label={label}>
        {emptyLabel}
      </p>
    );
  }

  return (
    <div>
      {/* Always present for more than one series: identity never rests on
          colour alone, and the swatch sits beside text in ordinary ink. */}
      <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1">
        {series.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              aria-hidden
              className="size-2.5 rounded-full"
              style={{ backgroundColor: s.color }}
            />
            {s.label}
          </li>
        ))}
      </ul>

      <ul className="space-y-2.5" aria-label={label}>
        {data.map((d, row) => {
          const total = totals[row];
          return (
            <li
              key={d.label}
              className="grid grid-cols-[minmax(6rem,9rem)_1fr_auto] items-center gap-3"
            >
              <span className="truncate text-sm text-foreground" title={d.label}>
                {d.label}
              </span>
              <span className="flex h-3 gap-0.5 overflow-hidden rounded-full bg-muted">
                {series.map((s) => {
                  const value = d.values[s.key] ?? 0;
                  if (value <= 0) return null;
                  const dim = hover !== null && hover !== s.key;
                  return (
                    <span
                      key={s.key}
                      className="h-3 rounded-full transition-[width,opacity]"
                      style={{
                        width: `${(value / max) * 100}%`,
                        backgroundColor: s.color,
                        opacity: dim ? 0.4 : 1,
                      }}
                      onMouseEnter={() => setHover(s.key)}
                      onMouseLeave={() => setHover(null)}
                      title={`${s.label}: ${value}`}
                    />
                  );
                })}
              </span>
              <span className="text-sm font-semibold tabular-nums text-foreground">
                {total}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
