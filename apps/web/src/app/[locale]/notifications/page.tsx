import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { NotificationsPage } from "@/components/notifications-page";
import { RequireAuth } from "@/components/require-auth";

export default async function Page({ params }: PageProps<"/[locale]/notifications">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <RequireAuth>
        <NotificationsPage />
      </RequireAuth>
    </Suspense>
  );
}
