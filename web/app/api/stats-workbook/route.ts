import { auth } from "@/auth";

const SCOPES = { platform: "platform.xlsx", municipality: "municipality.xlsx" } as const;
const RANGES = new Set(["7", "30", "90"]);
const LANGS = new Set(["he", "en"]);

/**
 * Hands back the usage workbook, keeping the API token server-side.
 *
 * A plain <a download> cannot carry a bearer token, and the workbook is built
 * by the API — that is where the charts are written and, more to the point,
 * where the permission check lives. This only relays it.
 */
export async function GET(request: Request) {
  const session = await auth();
  if (!session) return new Response("unauthorized", { status: 401 });

  const asked = new URL(request.url).searchParams;
  const scope = asked.get("scope") === "municipality" ? "municipality" : "platform";
  const range = asked.get("range") ?? "30";
  const lang = asked.get("lang") ?? "he";
  // Whitelisted rather than passed through: these land in an upstream URL.
  if (!RANGES.has(range) || !LANGS.has(lang)) {
    return new Response("bad_request", { status: 400 });
  }

  const upstream = await fetch(
    `${process.env.API_BASE_URL}/api/stats/${SCOPES[scope]}?range_days=${range}&lang=${lang}`,
    { headers: { Authorization: `Bearer ${session.apiToken}` }, cache: "no-store" },
  );

  if (!upstream.ok || !upstream.body) {
    return new Response(await upstream.text(), { status: upstream.status });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type":
        upstream.headers.get("content-type") ??
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition":
        upstream.headers.get("content-disposition") ??
        `attachment; filename="usage-${scope}-${range}d.xlsx"`,
      "Cache-Control": "no-store",
    },
  });
}
