"use client";

import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { createContext, useCallback, useContext, useState } from "react";
import type { ReactNode } from "react";
import { cn } from "@/components/ui";

/** Brief messages for things that succeeded or failed.
 *
 * Until now a failed delete was silent: the action returned an error, nobody
 * read it, and the page refreshed with the item still there. A toast is the
 * smallest thing that tells the truth without interrupting the person.
 *
 * Announced with aria-live so a screen reader hears it, and positioned at the
 * bottom centre, which is direction-neutral for Hebrew and English alike.
 */
type Variant = "error" | "success" | "info";

interface Toast {
  id: number;
  message: string;
  variant: Variant;
}

const ToastContext = createContext<
  ((message: string, variant?: Variant) => void) | null
>(null);

const AUTO_DISMISS_MS = 5000;

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback(
    (message: string, variant: Variant = "error") => {
      const id = nextId++;
      setToasts((current) => [...current, { id, message, variant }]);
      // Errors stay longer: the reader has to decide what to do about them,
      // while a success only needs acknowledging.
      const ms = variant === "error" ? AUTO_DISMISS_MS * 1.6 : AUTO_DISMISS_MS;
      setTimeout(() => dismiss(id), ms);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-6 z-[60] flex flex-col items-center gap-2 px-4"
      >
        {toasts.map((toast) => {
          const Icon =
            toast.variant === "error"
              ? AlertCircle
              : toast.variant === "success"
                ? CheckCircle2
                : Info;
          return (
            <div
              key={toast.id}
              role="status"
              className={cn(
                "pointer-events-auto flex w-full max-w-md items-start gap-2.5 rounded-lg border p-3 shadow-lg",
                toast.variant === "error" &&
                  "border-destructive/30 bg-destructive text-destructive-foreground",
                toast.variant === "success" &&
                  "border-border bg-card text-foreground",
                toast.variant === "info" && "border-border bg-card text-foreground",
              )}
            >
              <Icon className="mt-0.5 size-4 shrink-0" />
              <p className="flex-1 text-sm">{toast.message}</p>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                className="shrink-0 rounded p-0.5 opacity-70 hover:opacity-100"
                aria-label="✕"
              >
                <X className="size-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const show = useContext(ToastContext);
  if (!show) throw new Error("useToast must be used inside ToastProvider");
  return show;
}
