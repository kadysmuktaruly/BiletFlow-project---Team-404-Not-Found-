import { setRequestLocale } from "next-intl/server";

import { StaffPanel } from "@/components/organizer/staff-panel";

export default async function Page({ params }: PageProps<"/[locale]/organizer/events/[eventId]/staff">) {
  setRequestLocale((await params).locale);
  return <StaffPanel />;
}
