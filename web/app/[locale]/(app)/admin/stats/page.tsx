import { StatsDashboard } from "@/components/stats/stats-dashboard";
import { apiFetch } from "@/lib/api";
import type { StatsData } from "@/lib/stats-types";

export default async function AdminStatsPage({
  searchParams,
}: PageProps<"/[locale]/admin/stats">) {
  const sp = await searchParams;
  const range = typeof sp.range === "string" ? sp.range : "30";
  const data = await apiFetch<StatsData>(
    `/api/stats/municipality?range_days=${range}`,
  );
  return <StatsDashboard scope="municipality" data={data} />;
}
