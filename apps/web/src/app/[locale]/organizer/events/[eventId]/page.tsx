import { setRequestLocale } from "next-intl/server";

import { EventDetailsPanel } from "@/components/organizer/event-details-panel";

export default async function Page({ params }: PageProps<"/[locale]/organizer/events/[eventId]">) {
  setRequestLocale((await params).locale);
  return <EventDetailsPanel />;
}
