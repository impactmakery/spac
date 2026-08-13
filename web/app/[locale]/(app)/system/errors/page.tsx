import { apiFetch } from "@/lib/api";
import type { SystemErrors } from "@/lib/error-types";
import { ErrorsClient } from "./errors-client";

export default async function SystemErrorsPage() {
  const data = await apiFetch<SystemErrors>("/api/system/errors");
  return <ErrorsClient data={data} />;
}
