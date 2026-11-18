"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";

import { useEventDateTime, useMoney } from "@/lib/format";

import { Alert } from "./ui";

export type PublicEvent = Schemas["PublicEventRead"];
export type PublicTicketType = Schemas["PublicTicketTypeRead"];

/** The public event page body (SRS 4.2). `ticketSlot` replaces the read-only ticket list,
 * e.g. with the purchase form on the attendee page. */
export function EventView({
  event,
  ticketSlot,
}: {
  event: PublicEvent;
  ticketSlot?: React.ReactNode;
}) {
  const t = useTranslations("event.view");
  const money = useMoney();
  const when = useEventDateTime();
  const venue = event.venue;

  return (
    <article className="grid gap-8 lg:grid-cols-[1fr_22rem]">
      <div className="space-y-6">
        {event.cover_image_url && (
          // eslint-disable-next-line @next/next/no-img-element -- organizer-supplied URL, any host
          <img
            src={event.cover_image_url}
            alt=""
            className="aspect-[2/1] w-full rounded-lg border border-gray-200 object-cover"
          />
        )}
        <header className="space-y-2">
          {event.category && (
            <p className="text-sm font-medium uppercase tracking-wide text-gray-600">{event.category}</p>
          )}
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">{event.title}</h1>
        </header>
        {event.status === "cancelled" && <Alert kind="error">{t("cancelled")}</Alert>}
        <dl className="grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm font-medium text-gray-600">{t("when")}</dt>
            <dd className="text-gray-900">
              {when(event.starts_at, event.timezone)} – {when(event.ends_at, event.timezone)}
              <span className="block text-sm text-gray-600">{event.timezone}</span>
            </dd>
          </div>
          {venue && (
            <div>
              <dt className="text-sm font-medium text-gray-600">{t("where")}</dt>
              <dd className="text-gray-900">
                {venue.name}
                <span className="block text-sm text-gray-600">
                  {[venue.address_line1, venue.city].filter(Boolean).join(", ")}
                </span>
              </dd>
            </div>
          )}
          <div>
            <dt className="text-sm font-medium text-gray-600">{t("organizer")}</dt>
            <dd className="text-gray-900">
              {event.organizer.display_name}
              <a
                href={`mailto:${event.organizer.contact_email}`}
                className="block text-sm text-gray-700 underline"
              >
                {event.organizer.contact_email}
              </a>
            </dd>
          </div>
        </dl>
        {event.description && (
          <div className="whitespace-pre-line leading-relaxed text-gray-800">{event.description}</div>
        )}
      </div>

      <aside aria-labelledby="tickets-heading" className="space-y-3">
        <h2 id="tickets-heading" className="text-lg font-semibold text-gray-900">
          {t("tickets")}
        </h2>
        {ticketSlot ?? (
          <ul className="space-y-2">
            {event.ticket_types.length === 0 && <li className="text-gray-600">{t("noTickets")}</li>}
            {event.ticket_types.map((tt) => (
              <li key={tt.id} className="rounded-md border border-gray-200 bg-white p-3">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-medium text-gray-900">{tt.name}</span>
                  <span className="font-semibold text-gray-900">
                    {tt.is_free ? t("free") : money(tt.price_kzt)}
                  </span>
                </div>
                <p className="text-sm text-gray-600">
                  {tt.quantity_available === 0
                    ? t("soldOut")
                    : tt.on_sale
                      ? t("left", { count: tt.quantity_available })
                      : t("notOnSale")}
                </p>
              </li>
            ))}
          </ul>
        )}
      </aside>
    </article>
  );
}
