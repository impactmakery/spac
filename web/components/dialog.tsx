"use client";

import { X } from "lucide-react";
import type { ReactNode } from "react";
import { Card } from "@/components/ui";

export function Dialog({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        aria-hidden
        className="absolute inset-0 bg-foreground/30"
        onClick={onClose}
      />
      <Card className="relative z-10 w-full max-w-md p-6">
        <button
          onClick={onClose}
          className="absolute end-4 top-4 rounded-lg p-1 text-muted-foreground hover:bg-muted"
        >
          <X className="size-4" />
        </button>
        <h2 className="mb-4 text-lg font-semibold text-foreground">{title}</h2>
        {children}
      </Card>
    </div>
  );
}
