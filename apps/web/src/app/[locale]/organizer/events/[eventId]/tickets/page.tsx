import { setRequestLocale } from "next-intl/server";

import { TicketTypesPanel } from "@/components/organizer/ticket-types-panel";

export default async function Page({ params }: PageProps<"/[locale]/organizer/events/[eventId]/tickets">) {
  setRequestLocale((await params).locale);
  return <TicketTypesPanel />;
}
