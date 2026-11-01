import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { EditEventPage } from "@/components/organizer/edit-event-page";

export default async function Page({ params }: PageProps<"/[locale]/organizer/events/[eventId]">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <EditEventPage />
    </Suspense>
  );
}
