import type { ReactNode } from "react";
import { Card } from "@/components/ui";

/** A single number is not a chart — it is a hero number in a tile. */
export function StatTile({
  label,
  value,
  hint,
  icon,
  color,
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon?: ReactNode;
  /** The measure's own colour, the same one its line or bar carries below.
   *  A rule down the edge rather than a filled card: identity, not emphasis —
   *  six shouted tiles say no more than six quiet ones. */
  color?: string;
}) {
  return (
    <Card
      className="relative overflow-hidden p-4 ps-5"
      style={color ? { borderInlineStartColor: color, borderInlineStartWidth: 3 } : undefined}
    >
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        {icon && (
          <span style={color ? { color } : undefined} className="text-muted-foreground">
            {icon}
          </span>
        )}
      </div>
      <p className="mt-1.5 text-2xl font-bold tabular-nums text-foreground">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
    </Card>
  );
}
