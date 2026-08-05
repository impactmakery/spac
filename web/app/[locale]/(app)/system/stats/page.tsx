import { StatsDashboard } from "@/components/stats/stats-dashboard";
import { apiFetch } from "@/lib/api";
import type { PlatformStatsData } from "@/lib/stats-types";

export default async function SystemStatsPage({
  searchParams,
}: PageProps<"/[locale]/system/stats">) {
  const sp = await searchParams;
  const range = typeof sp.range === "string" ? sp.range : "30";
  const data = await apiFetch<PlatformStatsData>(
    `/api/stats/platform?range_days=${range}`,
  );
  return <StatsDashboard scope="platform" data={data} />;
}
