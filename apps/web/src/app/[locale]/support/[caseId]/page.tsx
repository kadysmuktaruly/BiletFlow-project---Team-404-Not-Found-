import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { RequireAuth } from "@/components/require-auth";
import { CasePage } from "@/components/support/case-page";

export default async function Page({ params }: PageProps<"/[locale]/support/[caseId]">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <RequireAuth>
        <CasePage />
      </RequireAuth>
    </Suspense>
  );
}
