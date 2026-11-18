import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { RequireAuth } from "@/components/require-auth";
import { SupportListPage } from "@/components/support/list-page";

export default async function Page({ params }: PageProps<"/[locale]/support">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <RequireAuth>
        <SupportListPage />
      </RequireAuth>
    </Suspense>
  );
}
