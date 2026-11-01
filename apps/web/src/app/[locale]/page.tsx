import { getTranslations, setRequestLocale } from "next-intl/server";

import { Link } from "@/i18n/navigation";

export default async function HomePage({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("home");

  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <h1 className="max-w-2xl text-4xl font-bold tracking-tight text-gray-900">{t("title")}</h1>
        <p className="max-w-2xl text-lg text-gray-700">{t("lead")}</p>
      </section>
      <section className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-gray-900">{t("forOrganizers")}</h2>
        <p className="mt-1 text-gray-700">{t("forOrganizersText")}</p>
        <Link
          href="/register"
          className="mt-4 inline-block rounded-md bg-gray-900 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-700"
        >
          {t("getStarted")}
        </Link>
      </section>
    </div>
  );
}
