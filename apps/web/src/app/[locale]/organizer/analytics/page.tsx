import { getTranslations, setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { AnalyticsDashboard } from "@/components/organizer/analytics-dashboard";
import { PageTitle } from "@/components/ui";

export default async function Page({ params }: PageProps<"/[locale]/organizer/analytics">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("analytics");
  return (
    <div>
      <PageTitle>{t("title")}</PageTitle>
      <Suspense>
        <AnalyticsDashboard />
      </Suspense>
    </div>
  );
}
