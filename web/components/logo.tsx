import { Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/components/ui";

export function LogoChip({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm",
        className,
      )}
    >
      <Sparkles className="size-5" />
    </span>
  );
}

export function LogoBlock() {
  const t = useTranslations("common");
  return (
    <div className="flex items-center gap-3">
      <LogoChip />
      <span>
        <span className="block text-lg font-bold leading-tight text-foreground">
          {t("appName")}
        </span>
        <span className="block text-xs text-muted-foreground">{t("programName")}</span>
      </span>
    </div>
  );
}
