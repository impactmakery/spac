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

/** CSV of the current view — UTF-8 BOM so Excel opens Hebrew correctly. */
export function toCsv(headers: string[], rows: (string | number)[][]): string {
  const escape = (v: string | number) => {
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return (
    "﻿" +
    [headers, ...rows].map((r) => r.map(escape).join(",")).join("\r\n")
  );
}
