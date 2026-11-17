import { setRequestLocale } from "next-intl/server";

import { AttendeesPanel } from "@/components/organizer/attendees-panel";

export default async function Page({ params }: PageProps<"/[locale]/organizer/events/[eventId]/attendees">) {
  setRequestLocale((await params).locale);
  return <AttendeesPanel />;
}
