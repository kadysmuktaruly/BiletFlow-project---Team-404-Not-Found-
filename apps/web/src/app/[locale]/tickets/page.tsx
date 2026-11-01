import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { RequireAuth } from "@/components/require-auth";
import { MyTicketsPage } from "@/components/attendee/my-tickets-page";

export default async function Page({ params }: PageProps<"/[locale]/tickets">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <RequireAuth>
        <MyTicketsPage />
      </RequireAuth>
    </Suspense>
  );
}
