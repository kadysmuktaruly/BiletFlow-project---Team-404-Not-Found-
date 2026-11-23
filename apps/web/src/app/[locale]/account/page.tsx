import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { AccountPage } from "@/components/account-page";
import { RequireAuth } from "@/components/require-auth";

export default async function Page({ params }: PageProps<"/[locale]/account">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <RequireAuth>
        <AccountPage />
      </RequireAuth>
    </Suspense>
  );
}
