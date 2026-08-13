"use client";

import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  FileWarning,
  Timer,
} from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { Fragment, type ReactNode, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { useToast } from "@/components/toast";
import { Bidi, Button, Card } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import { retryFailedDocument } from "@/app/[locale]/(app)/admin-actions";
import type { SystemErrors } from "@/lib/error-types";
import { fileFormat, stem } from "@/lib/filename";

/** Join what is actually there with " · ", so nothing missing leaves a stray dot. */
function joined(parts: ReactNode[]) {
  return parts.filter(Boolean).map((part, i) => (
    <Fragment key={i}>
      {i > 0 && " · "}
      {part}
    </Fragment>
  ));
}

/**
 * What is currently broken.
 *
 * Three lists rather than one stream, because the three have different owners:
 * a server error wants a developer, a document that would not index usually
 * wants somebody to re-save the file, and a failed job usually means the
 * weekly digest did not go out. Merging them would file things with different
 * remedies under one heading.
 */
export function ErrorsClient({ data }: { data: SystemErrors }) {
  const t = useTranslations("systemErrors");
  const format = useFormatter();
  const router = useRouter();
  const toast = useToast();
  const [open, setOpen] = useState<number | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const total =
    data.server_errors.length +
    data.failed_documents.length +
    data.failed_jobs.length;

  async function retry(id: string) {
    setBusy(id);
    const res = await retryFailedDocument(id);
    setBusy(null);
    // A page about things going wrong is the last place to claim a success it
    // did not have.
    if ("error" in res || !res.data?.requeued) {
      toast(t("retryFailed"), "error");
      return;
    }
    toast(t("retryQueued"), "success");
    router.refresh();
  }

  const when = (iso: string) =>
    format.dateTime(new Date(iso), { dateStyle: "short", timeStyle: "short" });

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <PageHeader title={t("title")} subtitle={t("subtitle")} />

      {total === 0 ? (
        <div className="mt-16 flex flex-col items-center text-center">
          <span className="flex size-16 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <CheckCircle2 className="size-7" />
          </span>
          <p className="mt-4 text-lg font-semibold text-foreground">
            {t("allClear")}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("allClearBody")}
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* --- documents first: this is the list an administrator can act on */}
          {data.failed_documents.length > 0 && (
            <Card className="p-5">
              <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold text-foreground">
                <FileWarning className="size-4 text-muted-foreground" />
                {t("documents", { count: data.failed_documents.length })}
              </h2>
              <p className="mb-4 text-xs text-muted-foreground">
                {t("documentsHelp")}
              </p>
              <ul className="divide-y divide-border">
                {data.failed_documents.map((d) => (
                  <li
                    key={d.id}
                    className="flex flex-wrap items-center justify-between gap-3 py-3"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-foreground">
                        {d.title}
                      </span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {joined([
                          // The extension travels on its own: inside one bidi
                          // run a Hebrew name ending "2026.pdf" lays out as
                          // "pdf.2026", which is unreadable.
                          fileFormat(d.filename) && (
                            <Bidi>{fileFormat(d.filename)}</Bidi>
                          ),
                          stem(d.filename) !== stem(d.title) && (
                            <Bidi>{stem(d.filename)}</Bidi>
                          ),
                          d.library && <Bidi>{d.library}</Bidi>,
                          <span key="when" className="whitespace-nowrap">
                            {when(d.updated_at)}
                          </span>,
                          // Only once it has been tried more than once: "0
                          // attempts" beside a failure reads as a contradiction.
                          d.attempts > 1 &&
                            t("attempts", { count: d.attempts }),
                        ])}
                      </span>
                      {d.error && (
                        <span className="mt-1 block text-xs text-destructive">
                          <Bidi>{d.error}</Bidi>
                        </span>
                      )}
                    </span>
                    <Button
                      variant="secondary"
                      className="shrink-0 px-3 py-1 text-xs"
                      disabled={busy === d.id}
                      onClick={() => retry(d.id)}
                    >
                      {t("retry")}
                    </Button>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {data.server_errors.length > 0 && (
            <Card className="p-5">
              <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold text-foreground">
                <AlertTriangle className="size-4 text-muted-foreground" />
                {t("server", { count: data.server_errors.length })}
              </h2>
              <p className="mb-4 text-xs text-muted-foreground">
                {t("serverHelp")}
              </p>
              <ul className="divide-y divide-border">
                {data.server_errors.map((e) => (
                  <li key={e.id} className="py-3">
                    <button
                      type="button"
                      onClick={() => setOpen(open === e.id ? null : e.id)}
                      className="flex w-full items-start gap-2 text-start"
                    >
                      <ChevronDown
                        className={`mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform ${
                          open === e.id ? "rotate-180" : ""
                        }`}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium text-foreground">
                          <Bidi>{e.error_type}</Bidi>
                          {" — "}
                          <Bidi>{e.message}</Bidi>
                        </span>
                        <span className="block truncate text-xs text-muted-foreground">
                          <Bidi>{`${e.method} ${e.path}`}</Bidi> ·{" "}
                          <span className="whitespace-nowrap">
                            {when(e.occurred_at)}
                          </span>
                          {e.user_email && (
                            <>
                              {" · "}
                              <Bidi>{e.user_email}</Bidi>
                            </>
                          )}
                        </span>
                      </span>
                    </button>
                    {open === e.id && e.traceback && (
                      // dir=ltr: a stack trace is code, and reading it
                      // right-to-left makes it unusable
                      <pre
                        dir="ltr"
                        className="mt-2 max-h-72 overflow-auto rounded-lg bg-muted p-3 text-start text-xs"
                      >
                        {e.traceback}
                      </pre>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {data.failed_jobs.length > 0 && (
            <Card className="p-5">
              <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold text-foreground">
                <Timer className="size-4 text-muted-foreground" />
                {t("jobs", { count: data.failed_jobs.length })}
              </h2>
              <p className="mb-4 text-xs text-muted-foreground">
                {t("jobsHelp")}
              </p>
              <ul className="divide-y divide-border">
                {data.failed_jobs.map((j) => (
                  <li key={`${j.job}-${j.period_key}`} className="py-3">
                    <span className="block text-sm font-medium text-foreground">
                      <Bidi>{j.job}</Bidi> · <Bidi>{j.period_key}</Bidi>
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      <span className="whitespace-nowrap">
                        {when(j.started_at)}
                      </span>
                    </span>
                    {j.error && (
                      <span className="mt-1 block text-xs text-destructive">
                        <Bidi>{j.error}</Bidi>
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
