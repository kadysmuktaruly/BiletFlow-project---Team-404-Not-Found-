import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { EventsListPage } from "@/components/attendee/events-list-page";

export default async function Page({ params }: PageProps<"/[locale]/events">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <EventsListPage />
    </Suspense>
  );
}
