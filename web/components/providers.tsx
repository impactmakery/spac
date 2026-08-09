"use client";

import { SessionProvider } from "next-auth/react";
import type { ReactNode } from "react";
import { ConfirmProvider } from "@/components/confirm";
import { ToastProvider } from "@/components/toast";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      {/* One confirmation dialog and one toast stack for the whole app, so any
          screen can ask before something irreversible, or report that it
          failed, without mounting its own. */}
      <ToastProvider>
        <ConfirmProvider>{children}</ConfirmProvider>
      </ToastProvider>
    </SessionProvider>
  );
}
