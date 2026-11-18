import { useTranslations } from "next-intl";

/** A quiet footer: the name and what the platform is for. */
export function SiteFooter() {
  const t = useTranslations("common");
  return (
    <footer className="mt-16 border-t border-line bg-surface">
      <div className="mx-auto flex max-w-6xl flex-wrap items-baseline justify-between gap-x-6 gap-y-1 px-4 py-8 sm:px-6">
        <p className="font-display text-lg text-ink">{t("appName")}</p>
        <p className="text-sm text-ink-muted">{t("tagline")}</p>
      </div>
    </footer>
  );
}
