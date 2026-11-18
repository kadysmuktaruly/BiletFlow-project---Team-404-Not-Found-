import { setRequestLocale } from "next-intl/server";

import { PreviewPanel } from "@/components/organizer/preview-panel";

export default async function Page({ params }: PageProps<"/[locale]/organizer/events/[eventId]/preview">) {
  setRequestLocale((await params).locale);
  return <PreviewPanel />;
}
