import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { NewEventPage } from "@/components/organizer/new-event-page";

export default async function Page({ params }: PageProps<"/[locale]/organizer/events/new">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <NewEventPage />
    </Suspense>
  );
}
