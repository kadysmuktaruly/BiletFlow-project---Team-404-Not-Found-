import { setRequestLocale } from "next-intl/server";

import { CampaignsPanel } from "@/components/organizer/campaigns-panel";

export default async function Page({ params }: PageProps<"/[locale]/organizer/events/[eventId]/campaigns">) {
  setRequestLocale((await params).locale);
  return <CampaignsPanel />;
}
