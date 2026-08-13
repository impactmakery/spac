export interface Kpis {
  active_users: number;
  chat_sessions: number;
  chat_messages: number;
  unanswered: number;
  unanswered_pct: number;
  board_items: number;
  comments: number;
  likes: number;
  files_uploaded: number;
}

export interface SeriesPoint {
  day: string;
  active_users: number;
  chat_messages: number;
}

export interface BreakdownRow {
  id: string;
  name: string;
  kpis: Kpis;
}

export interface StatsData {
  range_days: number;
  kpis: Kpis;
  series: SeriesPoint[];
  breakdown: BreakdownRow[];
}

export interface UnansweredRow {
  question: string;
  municipality_name: string | null;
  created_at: string;
}

export interface PlatformStatsData extends StatsData {
  unanswered_questions: UnansweredRow[];
}

const escape = (v: string | number) => {
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

/** UTF-8 BOM, so Excel opens Hebrew correctly. */
const BOM = "﻿";

/** CSV of one table. */
export function toCsv(headers: string[], rows: (string | number)[][]): string {
  return BOM + [headers, ...rows].map((r) => r.map(escape).join(",")).join("\r\n");
}

export interface CsvSection {
  title: string;
  headers: string[];
  rows: (string | number)[][];
}

/**
 * Everything on the page, in one file.
 *
 * The screen is a summary, two lines over time, a comparison and a list —
 * four shapes with no set of columns in common. Rather than four downloads,
 * or one table that suits none of them, each becomes a titled block with a
 * blank line between: what a spreadsheet expects, and what somebody pasting
 * one section into a report actually wants.
 *
 * A section with no rows is left out. An empty heading reads as data gone
 * missing rather than as nothing having happened.
 */
export function toSectionedCsv(sections: CsvSection[]): string {
  const blocks = sections
    .filter((s) => s.rows.length > 0)
    .map((s) =>
      [
        escape(s.title),
        s.headers.map(escape).join(","),
        ...s.rows.map((r) => r.map(escape).join(",")),
      ].join("\r\n"),
    );
  return BOM + blocks.join("\r\n\r\n") + "\r\n";
}
