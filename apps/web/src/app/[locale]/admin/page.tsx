import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { AdminPortal } from "@/components/admin/admin-portal";
import { RequireAuth } from "@/components/require-auth";

export default async function Page({ params }: PageProps<"/[locale]/admin">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <RequireAuth role="platform_admin">
        <AdminPortal />
      </RequireAuth>
    </Suspense>
  );
}
