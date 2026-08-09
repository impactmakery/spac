"use client";

import { AlertTriangle } from "lucide-react";
import { useTranslations } from "next-intl";
import { createContext, useCallback, useContext, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Button, Card, cn } from "@/components/ui";

/** A styled replacement for window.confirm.
 *
 * Promise-based on purpose: every call site already read
 * `if (!window.confirm(...)) return;`, so becoming
 * `if (!(await confirm({...}))) return;` leaves the surrounding logic alone.
 *
 * The layout is deliberately not the generic Dialog. A confirmation has a short
 * heading, an explanation, and two choices — and it should not offer a close
 * ✕ that means the same as Cancel but looks like a third option.
 */
interface ConfirmOptions {
  /** A few words. The explanation belongs in `body`. */
  title: string;
  body?: string;
  confirmLabel?: string;
  /** False for reversible things — deactivating rather than deleting. */
  destructive?: boolean;
}

const ConfirmContext = createContext<
  ((options: ConfirmOptions) => Promise<boolean>) | null
>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const t = useTranslations("common");
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const resolver = useRef<((ok: boolean) => void) | null>(null);

  const confirm = useCallback((next: ConfirmOptions) => {
    setOptions(next);
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
    });
  }, []);

  const settle = useCallback((answer: boolean) => {
    resolver.current?.(answer);
    resolver.current = null;
    setOptions(null);
  }, []);

  const destructive = options?.destructive !== false;

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {options && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[70] flex items-center justify-center p-4"
          onKeyDown={(e) => e.key === "Escape" && settle(false)}
        >
          <button
            aria-hidden
            tabIndex={-1}
            className="absolute inset-0 bg-foreground/40"
            onClick={() => settle(false)}
          />
          <Card className="relative z-10 w-full max-w-sm p-6">
            <div className="flex gap-4">
              <span
                aria-hidden
                className={cn(
                  "flex size-10 shrink-0 items-center justify-center rounded-full",
                  destructive
                    ? "bg-destructive/10 text-destructive"
                    : "bg-accent text-accent-foreground",
                )}
              >
                <AlertTriangle className="size-5" />
              </span>
              <div className="min-w-0 pt-1">
                <h2 className="text-base font-semibold text-foreground">
                  {options.title}
                </h2>
                {options.body && (
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                    {options.body}
                  </p>
                )}
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => settle(false)}>
                {t("cancel")}
              </Button>
              <Button
                type="button"
                autoFocus
                variant={destructive ? "destructive" : "primary"}
                onClick={() => settle(true)}
              >
                {options.confirmLabel ?? t("delete")}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const confirm = useContext(ConfirmContext);
  if (!confirm) {
    throw new Error("useConfirm must be used inside ConfirmProvider");
  }
  return confirm;
}
