import { setRequestLocale } from "next-intl/server";

import { OrdersPanel } from "@/components/organizer/orders-panel";

export default async function Page({ params }: PageProps<"/[locale]/organizer/events/[eventId]/orders">) {
  setRequestLocale((await params).locale);
  return <OrdersPanel />;
}
