"use client";

import { Check, Copy } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui";

/** A shared prompt is only useful if it can be taken away and used, so the copy
 *  button is the point of this block rather than a convenience. */
export function PromptBlock({ text }: { text: string }) {
  const t = useTranslations("board");
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be refused; the text is selectable either way.
    }
  }

  return (
    <div className="rounded-lg border border-border bg-muted/40">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <span className="text-xs font-medium text-muted-foreground">
          {t("promptHeading")}
        </span>
        <Button
          variant="ghost"
          type="button"
          onClick={copy}
          className="px-2 py-1 text-xs"
        >
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
          {copied ? t("copied") : t("copyPrompt")}
        </Button>
      </div>
      {/* dir="ltr" is wrong for a Hebrew prompt and right for everything else,
          so the direction is left to the browser's own detection. */}
      <pre className="max-h-96 overflow-auto whitespace-pre-wrap px-3 py-3 font-mono text-sm">
        {text}
      </pre>
    </div>
  );
}
