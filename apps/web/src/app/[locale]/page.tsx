import { getTranslations, setRequestLocale } from "next-intl/server";

import { buttonClass } from "@/components/ui";
import { Link } from "@/i18n/navigation";

/** Three tickets fanned out, in the poster colours. Decorative. */
function TicketFan() {
  const ticket = "absolute inset-x-6 h-40 rounded-poster";
  return (
    <div aria-hidden="true" className="relative hidden h-72 sm:block">
      <div className={`${ticket} top-2 -rotate-6 bg-sky`} />
      <div className={`${ticket} top-12 rotate-3 bg-sun`} />
      <div className={`${ticket} top-24 -rotate-2 bg-ink`}>
        <span className="absolute inset-y-5 right-16 border-l-2 border-dashed border-surface/40" />
        <span className="absolute -top-3 right-[3.25rem] h-6 w-6 rounded-full bg-paper" />
        <span className="absolute -bottom-3 right-[3.25rem] h-6 w-6 rounded-full bg-paper" />
      </div>
    </div>
  );
}

export default async function HomePage({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("home");

  return (
    <div className="space-y-12 sm:space-y-16">
      <section className="grid gap-10 pt-2 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-center">
        <div className="space-y-6">
          <h1 className="font-display max-w-3xl text-[clamp(2.5rem,1.4rem+4.6vw,4.75rem)] leading-[0.98] text-ink">
            {t("title")}
          </h1>
          <p className="max-w-[55ch] text-lg leading-relaxed text-ink-muted">{t("lead")}</p>
          <Link href="/events" className={`${buttonClass("primary")} min-h-12 px-7 text-base`}>
            {t("browse")}
          </Link>
        </div>
        <TicketFan />
      </section>
      <section className="on-dark grid gap-6 rounded-poster bg-ink p-6 text-surface sm:p-10 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <div className="space-y-2">
          <h2 className="font-display text-3xl">{t("forOrganizers")}</h2>
          <p className="max-w-[55ch] text-surface/85">{t("forOrganizersText")}</p>
        </div>
        <Link
          href="/register"
          className="inline-flex min-h-12 items-center justify-center rounded-full bg-sun px-7 font-semibold text-ink transition-transform hover:bg-sun/90 active:scale-[0.98]"
        >
          {t("getStarted")}
        </Link>
      </section>
    </div>
  );
}
