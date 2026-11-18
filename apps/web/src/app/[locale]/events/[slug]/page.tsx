import { Suspense } from "react";

import { EventPage } from "@/components/attendee/event-page";

// The [locale] layout sets the request locale. This page reads its dynamic param on the
// client (inside Suspense), so nothing here waits on request data during prerendering.
export default function Page() {
  return (
    <Suspense>
      <EventPage />
    </Suspense>
  );
}
