import { setRequestLocale } from "next-intl/server";

import { ActivationPanel } from "@/components/organizer/activation-panel";

export default async function Page({ params }: PageProps<"/[locale]/organizer/events/[eventId]/activation">) {
  setRequestLocale((await params).locale);
  return <ActivationPanel />;
}
