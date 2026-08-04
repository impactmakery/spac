import { Hourglass } from "lucide-react";
import { useTranslations } from "next-intl";

export function ComingSoon({ title }: { title: string }) {
  const t = useTranslations("common");
  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-3xl font-bold text-foreground">{title}</h1>
      <div className="mt-16 flex flex-col items-center text-center">
        <span className="flex size-16 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
          <Hourglass className="size-7" />
        </span>
        <p className="mt-4 text-lg font-semibold text-foreground">{t("comingSoon")}</p>
        <p className="mt-1 text-sm text-muted-foreground">{t("comingSoonBody")}</p>
      </div>
    </div>
  );
}
