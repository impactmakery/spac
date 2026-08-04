import { auth } from "@/auth";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail?: string,
  ) {
    super(`API ${status}${detail ? `: ${detail}` : ""}`);
  }
}

/** Server-side fetch to the FastAPI backend with the session's Bearer token. */
export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const session = await auth();
  const headers = new Headers(init.headers);
  if (session?.apiToken) headers.set("Authorization", `Bearer ${session.apiToken}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${process.env.API_BASE_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail: string | undefined;
    try {
      detail = (await res.json()).detail;
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
