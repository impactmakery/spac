"use client";

import { useFormatter } from "next-intl";
import { useId, useState } from "react";

export interface LinePoint {
  day: string;
  value: number;
}

/** Single-series time line: 2px stroke, recessive grid, crosshair + tooltip.
 *  One series means no legend box — the card title names it. */
export function LineChart({
  points,
  color = "var(--chart-1)",
  height = 180,
  label,
}: {
  points: LinePoint[];
  color?: string;
  height?: number;
  label: string;
}) {
  const format = useFormatter();
  const gradientId = useId();
  const [hover, setHover] = useState<number | null>(null);

  const width = 640;
  const pad = { top: 12, right: 12, bottom: 24, left: 32 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  if (points.length === 0) {
    return <div className="h-44 rounded-lg bg-muted/50" aria-label={label} />;
  }

  const max = Math.max(1, ...points.map((p) => p.value));
  const x = (i: number) =>
    pad.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
  const y = (v: number) => pad.top + innerH - (v / max) * innerH;

  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.value)}`).join(" ");
  const area =
    `${path} L${x(points.length - 1)},${pad.top + innerH} L${x(0)},${pad.top + innerH} Z`;
  const ticks = [0, max / 2, max];
  const active = hover != null ? points[hover] : null;

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label={label}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - rect.left) / rect.width) * width;
          const idx = Math.round(((px - pad.left) / innerW) * (points.length - 1));
          setHover(Math.max(0, Math.min(points.length - 1, idx)));
        }}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.18" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>

        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={pad.left}
              x2={width - pad.right}
              y1={y(t)}
              y2={y(t)}
              stroke="var(--chart-grid)"
              strokeWidth="1"
            />
            <text
              x={pad.left - 6}
              y={y(t) + 4}
              textAnchor="end"
              className="fill-[var(--muted-foreground)] text-[10px]"
            >
              {Math.round(t)}
            </text>
          </g>
        ))}

        <path d={area} fill={`url(#${gradientId})`} />
        <path
          d={path}
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {active && hover != null && (
          <>
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1={pad.top}
              y2={pad.top + innerH}
              stroke="var(--chart-grid)"
              strokeWidth="1"
            />
            <circle
              cx={x(hover)}
              cy={y(active.value)}
              r="5"
              fill={color}
              stroke="var(--card)"
              strokeWidth="2"
            />
          </>
        )}

        <text
          x={pad.left}
          y={height - 6}
          className="fill-[var(--muted-foreground)] text-[10px]"
        >
          {format.dateTime(new Date(points[0].day), { day: "numeric", month: "short" })}
        </text>
        <text
          x={width - pad.right}
          y={height - 6}
          textAnchor="end"
          className="fill-[var(--muted-foreground)] text-[10px]"
        >
          {format.dateTime(new Date(points[points.length - 1].day), {
            day: "numeric",
            month: "short",
          })}
        </text>
      </svg>

      {active && (
        <div className="pointer-events-none absolute top-2 end-2 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs shadow-sm">
          <span className="font-semibold text-foreground">{active.value}</span>{" "}
          <span className="text-muted-foreground">
            · {format.dateTime(new Date(active.day), { dateStyle: "medium" })}
          </span>
        </div>
      )}
    </div>
  );
}
