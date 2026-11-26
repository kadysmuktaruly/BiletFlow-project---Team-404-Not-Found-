import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { AccountPage } from "@/components/account-page";

export default async function Page({ params }: PageProps<"/[locale]/account">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <AccountPage />
    </Suspense>
  );
}
