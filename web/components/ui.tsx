import { clsx } from "clsx";
import type { ComponentProps, ReactNode } from "react";

export function cn(...args: Parameters<typeof clsx>) {
  return clsx(...args);
}

export function Button({
  className,
  variant = "primary",
  ...props
}: ComponentProps<"button"> & {
  variant?: "primary" | "secondary" | "ghost" | "destructive";
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium",
        "transition-colors focus-visible:outline-2 focus-visible:outline-ring",
        "disabled:pointer-events-none disabled:opacity-50",
        variant === "primary" && "bg-primary text-primary-foreground hover:bg-primary/90",
        variant === "secondary" &&
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        variant === "ghost" && "text-foreground hover:bg-muted",
        variant === "destructive" &&
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        className,
      )}
      {...props}
    />
  );
}

export function Input({ className, ...props }: ComponentProps<"input">) {
  return (
    <input
      className={cn(
        "w-full rounded-lg border border-input bg-card px-3 py-2 text-sm",
        "placeholder:text-muted-foreground",
        "focus-visible:outline-2 focus-visible:outline-ring",
        className,
      )}
      {...props}
    />
  );
}

export function Label({ className, ...props }: ComponentProps<"label">) {
  return (
    <label
      className={cn("mb-1.5 block text-sm font-medium text-foreground", className)}
      {...props}
    />
  );
}

export function FieldError({ children }: { children?: string | null }) {
  if (!children) return null;
  return <p className="mt-1.5 text-sm text-destructive">{children}</p>;
}

/**
 * Isolates a value from the direction of the text around it.
 *
 * Hebrew prose with Latin values inside it — a date, a file size, "DOCX", an
 * English name — is bidirectional, and the punctuation between them is
 * directionally neutral. The browser then places that punctuation by the
 * surrounding run rather than the value it belongs to, so "12 באוג׳ 2026"
 * renders as "12 ... באוג׳ 2026" with the day thrown to the far end of the
 * line, and "2026, 22:47" comes back as ",2026 22:47".
 *
 * <bdi> tells the browser to resolve each value's direction on its own. It is
 * one element with no styling and no cost, and it is the difference between a
 * date a Hebrew reader trusts and one they do not.
 */
export function Bidi({ children }: { children: ReactNode }) {
  return <bdi>{children}</bdi>;
}

export function Card({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn("rounded-xl border border-border bg-card shadow-sm", className)}
      {...props}
    />
  );
}

export function Badge({
  className,
  tone = "muted",
  ...props
}: ComponentProps<"span"> & { tone?: "muted" | "accent" | "destructive" | "primary" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        tone === "muted" && "bg-muted text-muted-foreground",
        tone === "accent" && "bg-accent text-accent-foreground",
        tone === "destructive" && "bg-destructive/10 text-destructive",
        tone === "primary" && "bg-primary text-primary-foreground",
        className,
      )}
      {...props}
    />
  );
}

export function Select({ className, ...props }: ComponentProps<"select">) {
  return (
    <select
      className={cn(
        "rounded-lg border border-input bg-card px-3 py-2 text-sm",
        "focus-visible:outline-2 focus-visible:outline-ring",
        className,
      )}
      {...props}
    />
  );
}
