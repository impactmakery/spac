"use client";

import { BarChart3, Download, FileText, MessageCircle, Users } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { BarChart } from "@/components/charts/bar-chart";
import { StackedBar } from "@/components/charts/stacked-bar";
import { LineChart } from "@/components/charts/line-chart";
import { StatTile } from "@/components/charts/stat-tile";
import { PageHeader } from "@/components/page-header";
import { Button, Card, Select, cn } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import {
  toCsv,
  type BreakdownRow,
  type PlatformStatsData,
  type StatsData,
} from "@/lib/stats-types";

const RANGES = [7, 30, 90] as const;

/**
 * What the comparison bars measure.
 *
 * It used to be chat_messages + board_items with nothing on screen saying so,
 * which is two problems at once: the reader could not know what the number
 * meant, and the number itself added two unlike things — ten questions and no
 * posts scored the same as ten posts and no questions.
 *
 * Every one of these is already a figure shown in the tiles above, so a bar
 * can now be checked against a total the reader has just read.
 */
const COMPARABLE = [
  { key: "chat_messages", label: "chatMessages" },
  { key: "active_users", label: "activeUsers" },
  { key: "board_items", label: "boardItems" },
  { key: "files_uploaded", label: "filesUploaded" },
] as const;

type Comparable = (typeof COMPARABLE)[number]["key"];

export function StatsDashboard({
  scope,
  data,
}: {
  scope: "municipality" | "platform";
  data: StatsData | PlatformStatsData;
}) {
  const t = useTranslations("stats");
  const router = useRouter();
  const [compareBy, setCompareBy] = useState<Comparable>("chat_messages");
  const basePath = scope === "platform" ? "/system/stats" : "/admin/stats";
  const unanswered =
    "unanswered_questions" in data ? data.unanswered_questions : null;

  const hasData =
    data.kpis.active_users + data.kpis.chat_messages + data.kpis.board_items > 0;

  function exportCsv() {
    const headers = [
      scope === "platform" ? t("municipality") : t("department"),
      t("activeUsers"),
      t("chatSessions"),
      t("chatMessages"),
      t("unansweredPct"),
      t("boardItems"),
      t("comments"),
      t("likes"),
      t("filesUploaded"),
    ];
    const row = (r: BreakdownRow) => [
      r.name,
      r.kpis.active_users,
      r.kpis.chat_sessions,
      r.kpis.chat_messages,
      r.kpis.unanswered_pct,
      r.kpis.board_items,
      r.kpis.comments,
      r.kpis.likes,
      r.kpis.files_uploaded,
    ];
    const csv = toCsv(headers, data.breakdown.map(row));
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `usage-${scope}-${data.range_days}d.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <PageHeader
        title={t("title")}
        subtitle={
          scope === "platform" ? t("subtitlePlatform") : t("subtitleMunicipality")
        }
        action={
          <Button variant="secondary" onClick={exportCsv}>
            <Download className="size-4" />
            {t("exportCsv")}
          </Button>
        }
      />

      <div className="mb-6 flex gap-2">
        {RANGES.map((r) => (
          <button
            key={r}
            onClick={() => router.push(`${basePath}?range=${r}`)}
            className={cn(
              "rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
              data.range_days === r
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-accent",
            )}
          >
            {t(`range${r}` as "range7" | "range30" | "range90")}
          </button>
        ))}
      </div>

      {!hasData ? (
        <div className="mt-16 flex flex-col items-center text-center">
          <span className="flex size-16 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <BarChart3 className="size-7" />
          </span>
          <p className="mt-4 text-lg font-semibold text-foreground">{t("empty")}</p>
          <p className="mt-1 text-sm text-muted-foreground">{t("emptyBody")}</p>
        </div>
      ) : (
        <>
          <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <StatTile
              label={t("activeUsers")}
              value={data.kpis.active_users}
              icon={<Users className="size-4" />}
            />
            <StatTile
              label={t("chatSessions")}
              value={data.kpis.chat_sessions}
              icon={<MessageCircle className="size-4" />}
            />
            <StatTile label={t("chatMessages")} value={data.kpis.chat_messages} />
            <StatTile
              label={t("unansweredPct")}
              value={`${data.kpis.unanswered_pct}%`}
              hint={`${data.kpis.unanswered} / ${data.kpis.chat_messages}`}
            />
            <StatTile label={t("boardItems")} value={data.kpis.board_items} />
            <StatTile
              label={t("filesUploaded")}
              value={data.kpis.files_uploaded}
              icon={<FileText className="size-4" />}
            />
          </div>

          {/* two measures of different scale => two charts, never a dual axis */}
          <div className="mb-6 grid gap-4 lg:grid-cols-2">
            <Card className="p-5">
              <h2 className="mb-3 text-sm font-semibold text-foreground">
                {t("activeUsersOverTime")}
              </h2>
              <LineChart
                label={t("activeUsersOverTime")}
                points={data.series.map((s) => ({
                  day: s.day,
                  value: s.active_users,
                }))}
                color="var(--chart-1)"
              />
            </Card>
            <Card className="p-5">
              <h2 className="mb-3 text-sm font-semibold text-foreground">
                {t("chatVolumeOverTime")}
              </h2>
              <LineChart
                label={t("chatVolumeOverTime")}
                points={data.series.map((s) => ({
                  day: s.day,
                  value: s.chat_messages,
                }))}
                color="var(--chart-3)"
              />
            </Card>
          </div>

          <Card className="mb-6 p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-foreground">
                {scope === "platform" ? t("byMunicipality") : t("byDepartment")}
              </h2>
              {/* Naming the measure is the point: a bar chart of an unlabelled
                  number tells the reader nothing they can act on. */}
              <Select
                aria-label={t("comparing")}
                value={compareBy}
                onChange={(e) => setCompareBy(e.target.value as Comparable)}
              >
                {COMPARABLE.map((m) => (
                  <option key={m.key} value={m.key}>
                    {t(m.label)}
                  </option>
                ))}
              </Select>
            </div>
            <BarChart
              label={`${scope === "platform" ? t("byMunicipality") : t("byDepartment")} — ${t(
                COMPARABLE.find((m) => m.key === compareBy)!.label,
              )}`}
              data={data.breakdown.map((b) => ({
                label: b.name,
                value: b.kpis[compareBy],
              }))}
              color="var(--chart-1)"
            />
            <p className="mt-3 text-xs text-muted-foreground">
              {t("comparingHelp", {
                metric: t(COMPARABLE.find((m) => m.key === compareBy)!.label),
                grouping: scope === "platform" ? t("municipality") : t("department"),
                days: data.range_days,
              })}
            </p>
          </Card>

          {/* Composition, not magnitude: the chart above answers "who does most
              of X", this one answers "what is each one actually doing". Stacked
              rather than a pie — there are more rows than a pie can carry, most
              of them near zero, and the labels are long Hebrew names. */}
          <Card className="mb-6 p-5">
            <h2 className="mb-1 text-sm font-semibold text-foreground">
              {t("activityMix")}
            </h2>
            <p className="mb-4 text-xs text-muted-foreground">
              {t("activityMixHelp", { days: data.range_days })}
            </p>
            <StackedBar
              label={t("activityMix")}
              emptyLabel={t("empty")}
              series={[
                { key: "chat_messages", label: t("chatMessages"), color: "var(--chart-1)" },
                { key: "board_items", label: t("boardItems"), color: "var(--chart-2)" },
                { key: "files_uploaded", label: t("filesUploaded"), color: "var(--chart-3)" },
              ]}
              data={data.breakdown.map((b) => ({
                label: b.name,
                values: {
                  chat_messages: b.kpis.chat_messages,
                  board_items: b.kpis.board_items,
                  files_uploaded: b.kpis.files_uploaded,
                },
              }))}
            />
          </Card>

          {/* the table view is also the accessible fallback for the charts */}
          <Card className="mb-6 overflow-x-auto">
            <h2 className="p-5 pb-3 text-sm font-semibold text-foreground">
              {t("tableView")}
            </h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="p-3 text-start font-medium">
                    {scope === "platform" ? t("municipality") : t("department")}
                  </th>
                  <th className="p-3 text-start font-medium">{t("activeUsers")}</th>
                  <th className="p-3 text-start font-medium">{t("chatMessages")}</th>
                  <th className="p-3 text-start font-medium">{t("unansweredPct")}</th>
                  <th className="p-3 text-start font-medium">{t("boardItems")}</th>
                  <th className="p-3 text-start font-medium">{t("filesUploaded")}</th>
                </tr>
              </thead>
              <tbody>
                {data.breakdown.map((row) => (
                  <tr key={row.id} className="border-b border-border last:border-0">
                    <td className="p-3 font-medium text-foreground">{row.name}</td>
                    <td className="p-3 tabular-nums">{row.kpis.active_users}</td>
                    <td className="p-3 tabular-nums">{row.kpis.chat_messages}</td>
                    <td className="p-3 tabular-nums">{row.kpis.unanswered_pct}%</td>
                    <td className="p-3 tabular-nums">{row.kpis.board_items}</td>
                    <td className="p-3 tabular-nums">{row.kpis.files_uploaded}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          {unanswered && (
            <Card className="p-5">
              <h2 className="text-sm font-semibold text-foreground">
                {t("unansweredPanel")}
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                {t("unansweredHelp")}
              </p>
              {unanswered.length === 0 ? (
                <p className="mt-4 text-sm text-muted-foreground">
                  {t("noUnanswered")}
                </p>
              ) : (
                <ul className="mt-4 space-y-2">
                  {unanswered.map((u, i) => (
                    <li
                      key={`${u.question}-${i}`}
                      className="flex items-start justify-between gap-3 border-b border-border pb-2 last:border-0"
                    >
                      <span className="text-sm text-foreground">{u.question}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {u.municipality_name ?? "—"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  );
}
