import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { MyOrdersPage } from "@/components/attendee/my-orders-page";
import { RequireAuth } from "@/components/require-auth";

export default async function Page({ params }: PageProps<"/[locale]/orders">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <RequireAuth>
        <MyOrdersPage />
      </RequireAuth>
    </Suspense>
  );
}
