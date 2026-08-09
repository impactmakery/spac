"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { Dialog } from "@/components/dialog";
import { Button } from "@/components/ui";

/** A styled replacement for window.confirm.
 *
 * It is promise-based on purpose: every call site already read
 * `if (!window.confirm(...)) return;`, so becoming
 * `if (!(await confirm({...}))) return;` leaves the surrounding logic alone.
 * Threading dialog state through nine components by hand would have been a far
 * larger change for the same result.
 *
 * window.confirm is unstyled, ignores the app's right-to-left direction, cannot
 * say what is about to be lost, and is suppressible by the browser.
 */
interface ConfirmOptions {
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
  const [busy, setBusy] = useState(false);
  const resolver = useRef<((ok: boolean) => void) | null>(null);

  const confirm = useCallback((next: ConfirmOptions) => {
    setOptions(next);
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
    });
  }, []);

  function settle(answer: boolean) {
    resolver.current?.(answer);
    resolver.current = null;
    setOptions(null);
    setBusy(false);
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Dialog
        open={options !== null}
        onClose={() => settle(false)}
        title={options?.title ?? ""}
      >
        {options?.body && (
          <p className="text-sm text-muted-foreground">{options.body}</p>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <Button
            type="button"
            variant="secondary"
            disabled={busy}
            onClick={() => settle(false)}
          >
            {t("cancel")}
          </Button>
          <Button
            type="button"
            variant={options?.destructive === false ? "primary" : "destructive"}
            disabled={busy}
            onClick={() => {
              // The caller does the work after this resolves, so the button
              // disables itself rather than waiting on something it cannot see.
              setBusy(true);
              settle(true);
            }}
          >
            {options?.confirmLabel ?? t("delete")}
          </Button>
        </div>
      </Dialog>
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
