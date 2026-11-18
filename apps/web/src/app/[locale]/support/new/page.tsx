import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { RequireAuth } from "@/components/require-auth";
import { NewCasePage } from "@/components/support/new-case-page";

export default async function Page({ params }: PageProps<"/[locale]/support/new">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <RequireAuth>
        <NewCasePage />
      </RequireAuth>
    </Suspense>
  );
}
