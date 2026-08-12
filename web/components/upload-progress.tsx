"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";

export interface UploadState {
  /** How many files have finished, successfully or not. */
  done: number;
  total: number;
  /** The file being sent right now. */
  current: string;
  failed: number;
}

/**
 * What is happening during a multi-file upload.
 *
 * Each file is a separate request, so a folder of twenty takes a while. Without
 * this the only sign of life was a disabled button — indistinguishable from a
 * page that had frozen, which is exactly what it looked like.
 */
export function UploadProgress({ state }: { state: UploadState }) {
  const t = useTranslations("knowledge");
  // Count the file in flight, so the bar moves as soon as the first one starts
  // rather than sitting at zero through the whole of it.
  const percent = Math.round(((state.done + 0.5) / state.total) * 100);

  return (
    <div
      className="mb-4 rounded-lg border border-border bg-card p-4"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-3">
        <Loader2 className="size-4 shrink-0 animate-spin text-muted-foreground" />
        <p className="min-w-0 flex-1 truncate text-sm text-foreground">{state.current}</p>
        <p className="shrink-0 text-sm tabular-nums text-muted-foreground">
          {t("uploadingCount", { done: state.done, total: state.total })}
        </p>
      </div>

      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-300"
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>

      {state.failed > 0 && (
        <p className="mt-2 text-xs text-destructive">
          {t("uploadingFailed", { count: state.failed })}
        </p>
      )}
    </div>
  );
}
