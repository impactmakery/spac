/**
 * The usage page as one file you can send someone.
 *
 * Built from the data rather than scraped out of the page. The charts on
 * screen are a mix — the time series is SVG, the comparisons are HTML with
 * Tailwind classes — so a clone would arrive at a file with no stylesheet and
 * fall apart. Drawing them again with inline styles costs a little arithmetic
 * and buys a file that is self-contained, testable, and does not break the
 * next time a class name changes.
 *
 * The result opens in a browser, prints to PDF as it stands, and pastes into
 * Word or Google Docs with its tables and charts intact.
 */

export interface ReportSeriesPoint {
  day: string;
  active_users: number;
  chat_messages: number;
}

export interface ReportBar {
  name: string;
  value: number;
}

export interface ReportStack {
  name: string;
  parts: { label: string; value: number; color: string }[];
}

export interface ReportTable {
  headers: string[];
  rows: (string | number)[][];
}

export interface ReportInput {
  dir: "rtl" | "ltr";
  lang: string;
  title: string;
  subtitle: string;
  /** "30 days", already in the reader's language. */
  rangeLabel: string;
  generatedLabel: string;
  tiles: { label: string; value: string; hint?: string }[];
  lines: { title: string; color: string; points: { day: string; value: number }[] }[];
  bars: { title: string; caption: string; items: ReportBar[] } | null;
  stacks: { title: string; caption: string; items: ReportStack[] } | null;
  table: { title: string } & ReportTable;
  unanswered: ({ title: string; caption: string } & ReportTable) | null;
}

/** The page's own chart palette, as literal values — a var() would resolve to
 *  nothing once the file leaves the app. */
export const REPORT_COLORS = ["#0b9488", "#d97706", "#4f46e5"] as const;

const INK = "#1c1b2e";
const MUTED = "#6b6b7b";
const BORDER = "#e0e0e0";
const TRACK = "#f0efeb";

export function escapeHtml(value: string | number): string {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * One series over time, as an SVG.
 *
 * Laid out left-to-right whatever the page direction: a time axis runs with
 * the dates, not with the script, and a Hebrew reader still expects the
 * earliest day at the left of a chart.
 */
function lineChart(
  points: { day: string; value: number }[],
  color: string,
  label: string,
): string {
  const w = 640;
  const h = 180;
  const pad = { top: 12, right: 12, bottom: 26, left: 36 };
  const innerW = w - pad.left - pad.right;
  const innerH = h - pad.top - pad.bottom;
  const max = Math.max(1, ...points.map((p) => p.value));
  const x = (i: number) =>
    pad.left + (points.length <= 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
  const y = (v: number) => pad.top + innerH - (v / max) * innerH;

  const line = points.map((p, i) => `${x(i)},${y(p.value)}`).join(" ");
  const area = `${pad.left},${pad.top + innerH} ${line} ${x(points.length - 1)},${
    pad.top + innerH
  }`;

  // Two gridlines and their labels: enough to read a value off, few enough to
  // stay out of the way.
  const ticks = [0, max].map(
    (v) => `
      <line x1="${pad.left}" y1="${y(v)}" x2="${w - pad.right}" y2="${y(v)}"
            stroke="${BORDER}" stroke-width="1" />
      <text x="${pad.left - 6}" y="${y(v) + 3}" text-anchor="end"
            font-size="10" fill="${MUTED}">${v}</text>`,
  );

  const first = points[0]?.day ?? "";
  const last = points[points.length - 1]?.day ?? "";

  return `
  <svg viewBox="0 0 ${w} ${h}" width="100%" role="img" aria-label="${escapeHtml(label)}"
       style="direction:ltr">
    ${ticks.join("")}
    <polygon points="${area}" fill="${color}" fill-opacity="0.10" />
    <polyline points="${line}" fill="none" stroke="${color}" stroke-width="2"
              stroke-linejoin="round" stroke-linecap="round" />
    <text x="${pad.left}" y="${h - 8}" font-size="10" fill="${MUTED}">${escapeHtml(first)}</text>
    <text x="${w - pad.right}" y="${h - 8}" font-size="10" fill="${MUTED}"
          text-anchor="end">${escapeHtml(last)}</text>
  </svg>`;
}

/** Horizontal bars: long municipality names need the room a column chart
 *  cannot give them. */
function barRows(items: ReportBar[]): string {
  const max = Math.max(1, ...items.map((i) => i.value));
  return items
    .map(
      (i) => `
      <tr>
        <td class="bar-name">${escapeHtml(i.name)}</td>
        <td class="bar-cell">
          <span class="track"><span class="fill" style="width:${
            (i.value / max) * 100
          }%;background:${REPORT_COLORS[0]}"></span></span>
        </td>
        <td class="bar-value">${i.value}</td>
      </tr>`,
    )
    .join("");
}

/** Part-to-whole, with a 2px gap between segments so adjacent fills stay
 *  distinguishable without an outline. */
function stackRows(items: ReportStack[]): string {
  const totals = items.map((i) => i.parts.reduce((a, p) => a + p.value, 0));
  const max = Math.max(1, ...totals);
  return items
    .map((item, idx) => {
      const total = totals[idx];
      const segments = item.parts
        .filter((p) => p.value > 0)
        .map(
          (p) => `<span class="seg" title="${escapeHtml(p.label)}"
                 style="flex:${p.value};background:${p.color}"></span>`,
        )
        .join("");
      return `
      <tr>
        <td class="bar-name">${escapeHtml(item.name)}</td>
        <td class="bar-cell">
          <span class="track"><span class="stack" style="width:${
            (total / max) * 100
          }%">${segments}</span></span>
        </td>
        <td class="bar-value">${total}</td>
      </tr>`;
    })
    .join("");
}

function table({ headers, rows }: ReportTable): string {
  return `
  <table class="data">
    <thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("")}</tr></thead>
    <tbody>
      ${rows
        .map(
          (r) => `<tr>${r.map((c) => `<td>${escapeHtml(c)}</td>`).join("")}</tr>`,
        )
        .join("")}
    </tbody>
  </table>`;
}

function legend(parts: { label: string; color: string }[]): string {
  return `<p class="legend">${parts
    .map(
      (p) =>
        `<span><i style="background:${p.color}"></i>${escapeHtml(p.label)}</span>`,
    )
    .join("")}</p>`;
}

export function buildReportHtml(input: ReportInput): string {
  const {
    dir,
    lang,
    title,
    subtitle,
    rangeLabel,
    generatedLabel,
    tiles,
    lines,
    bars,
    stacks,
    table: breakdown,
    unanswered,
  } = input;

  const stackLegend =
    stacks && stacks.items[0]
      ? legend(stacks.items[0].parts.map((p) => ({ label: p.label, color: p.color })))
      : "";

  return `<!doctype html>
<html lang="${escapeHtml(lang)}" dir="${dir}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)} — ${escapeHtml(rangeLabel)}</title>
<style>
  :root { color-scheme: light; }
  body {
    margin: 0; padding: 32px;
    font: 14px/1.5 "Segoe UI", system-ui, -apple-system, Arial, sans-serif;
    color: ${INK}; background: #fff;
  }
  .sheet { max-width: 900px; margin: 0 auto; }
  h1 { font-size: 26px; margin: 0 0 4px; }
  h2 { font-size: 15px; margin: 0 0 2px; }
  .sub, .caption { color: ${MUTED}; margin: 0; }
  .caption { font-size: 12px; margin-bottom: 12px; }
  .meta { color: ${MUTED}; font-size: 12px; margin: 4px 0 24px; }
  section { margin-bottom: 28px; page-break-inside: avoid; }
  .tiles { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 28px; }
  .tile {
    flex: 1 1 150px; border: 1px solid ${BORDER}; border-radius: 10px; padding: 12px 14px;
  }
  .tile .label { color: ${MUTED}; font-size: 12px; }
  .tile .value { font-size: 24px; font-weight: 700; margin-top: 2px; }
  .tile .hint { color: ${MUTED}; font-size: 11px; margin-top: 2px; }
  table { border-collapse: collapse; width: 100%; }
  table.data th, table.data td {
    border-bottom: 1px solid ${BORDER}; padding: 7px 10px; text-align: start;
  }
  table.data th { color: ${MUTED}; font-weight: 600; font-size: 12px; }
  table.data td { font-variant-numeric: tabular-nums; }
  .bar-name { width: 30%; padding: 5px 0; }
  .bar-cell { padding: 5px 10px; }
  .bar-value { width: 1%; text-align: end; font-weight: 600;
               font-variant-numeric: tabular-nums; white-space: nowrap; }
  /* The track stays visible behind an empty bar: a row with nothing in it
     should read as a measured zero, not as a row that failed to draw. */
  .track { display: block; height: 10px; border-radius: 999px; background: ${TRACK}; }
  .fill { display: block; height: 10px; border-radius: 999px; }
  .stack { display: flex; gap: 2px; height: 10px; border-radius: 999px;
           overflow: hidden; }
  .seg { display: block; height: 10px; min-width: 0; }
  .legend { display: flex; flex-wrap: wrap; gap: 14px; color: ${MUTED};
            font-size: 12px; margin: 0 0 10px; }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .legend i { width: 10px; height: 10px; border-radius: 999px; display: inline-block; }
  @media print {
    body { padding: 0; }
    section { break-inside: avoid; }
  }
</style>
</head>
<body>
<div class="sheet">
  <h1>${escapeHtml(title)}</h1>
  <p class="sub">${escapeHtml(subtitle)}</p>
  <p class="meta">${escapeHtml(rangeLabel)} · ${escapeHtml(generatedLabel)}</p>

  <div class="tiles">
    ${tiles
      .map(
        (k) => `<div class="tile">
      <div class="label">${escapeHtml(k.label)}</div>
      <div class="value">${escapeHtml(k.value)}</div>
      ${k.hint ? `<div class="hint">${escapeHtml(k.hint)}</div>` : ""}
    </div>`,
      )
      .join("")}
  </div>

  ${lines
    .map(
      (l) => `<section>
    <h2>${escapeHtml(l.title)}</h2>
    ${lineChart(l.points, l.color, l.title)}
  </section>`,
    )
    .join("")}

  ${
    bars
      ? `<section>
    <h2>${escapeHtml(bars.title)}</h2>
    <p class="caption">${escapeHtml(bars.caption)}</p>
    <table>${barRows(bars.items)}</table>
  </section>`
      : ""
  }

  ${
    stacks
      ? `<section>
    <h2>${escapeHtml(stacks.title)}</h2>
    <p class="caption">${escapeHtml(stacks.caption)}</p>
    ${stackLegend}
    <table>${stackRows(stacks.items)}</table>
  </section>`
      : ""
  }

  <section>
    <h2>${escapeHtml(breakdown.title)}</h2>
    ${table(breakdown)}
  </section>

  ${
    unanswered
      ? `<section>
    <h2>${escapeHtml(unanswered.title)}</h2>
    <p class="caption">${escapeHtml(unanswered.caption)}</p>
    ${table(unanswered)}
  </section>`
      : ""
  }
</div>
</body>
</html>`;
}
