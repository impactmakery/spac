"use client";

import { Paperclip, UploadCloud, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { cn } from "@/components/ui";
import { formatBytes } from "@/lib/format";

/** Drop a file, or click to pick one.
 *
 * The browser's own file input reads "Choose File / No file chosen", which
 * looks unfinished next to the rest of the form and gives no hint that
 * dragging works. The real input is still there, just visually hidden, so
 * keyboard focus and accessibility behave normally.
 */
export function FileDrop({
  file,
  onFile,
  hint,
}: {
  file: File | null;
  onFile: (file: File | null) => void;
  hint?: string;
}) {
  const t = useTranslations("board");
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function pick(files: FileList | null) {
    onFile(files?.[0] ?? null);
  }

  if (file) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-muted/40 px-3 py-2.5">
        <span className="flex min-w-0 items-center gap-2">
          <Paperclip className="size-4 shrink-0 text-muted-foreground" />
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-foreground">
              {file.name}
            </span>
            <span className="block text-xs text-muted-foreground">
              {formatBytes(file.size)}
            </span>
          </span>
        </span>
        <button
          type="button"
          onClick={() => {
            onFile(null);
            if (inputRef.current) inputRef.current.value = "";
          }}
          aria-label={t("removeFile")}
          title={t("removeFile")}
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
        >
          <X className="size-4" />
        </button>
      </div>
    );
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        pick(e.dataTransfer.files);
      }}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      role="button"
      tabIndex={0}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed px-4 py-7 text-center",
        "transition-colors focus-visible:outline-2 focus-visible:outline-ring",
        dragging
          ? "border-primary bg-primary/5"
          : "border-border bg-muted/20 hover:border-primary/50 hover:bg-muted/40",
      )}
    >
      <UploadCloud className="size-6 text-muted-foreground" />
      <p className="text-sm font-medium text-foreground">{t("dropTitle")}</p>
      <p className="text-xs text-muted-foreground">{t("dropBrowse")}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      <input
        ref={inputRef}
        type="file"
        className="sr-only"
        onChange={(e) => pick(e.target.files)}
      />
    </div>
  );
}
