"use client";

import { X } from "lucide-react";
import type { ReactNode } from "react";
import { Card } from "@/components/ui";

export function Dialog({
  open,
  onClose,
  title,
  children,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** Room for two columns, for forms that would otherwise be a long scroll. */
  wide?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        aria-hidden
        className="absolute inset-0 bg-foreground/30"
        onClick={onClose}
      />
      {/*
        Bounded and scrollable. Without a ceiling a tall form — the publish
        dialog once a file field appears — grew past the viewport with nowhere
        to scroll, so it filled the screen and pushed its own buttons out of
        reach. dvh rather than vh because a mobile browser's address bar makes
        vh taller than what you can actually see.

        The title and close button sit outside the scrolling region, so they
        stay put instead of sliding away as the form is filled in.
      */}
      <Card
        className={`relative z-10 flex max-h-[calc(100dvh-2rem)] w-full flex-col p-6 ${
          wide ? "max-w-3xl" : "max-w-md"
        }`}
      >
        <button
          onClick={onClose}
          className="absolute end-4 top-4 rounded-lg p-1 text-muted-foreground hover:bg-muted"
        >
          <X className="size-4" />
        </button>
        <h2 className="mb-4 shrink-0 pe-8 text-lg font-semibold text-foreground">
          {title}
        </h2>
        {/* -mx-1 px-1 so a focus ring on an edge control is not clipped */}
        <div className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1">{children}</div>
      </Card>
    </div>
  );
}
