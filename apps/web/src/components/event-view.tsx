"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";

import { useEventDateTime, useMoney } from "@/lib/format";

import { Poster } from "./event-card";
import { Alert, Badge, LINK, PriceTag, SECTION_TITLE } from "./ui";

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
    <article className="space-y-10">
      <div className="grid gap-6 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] md:items-end md:gap-10">
        <Poster
          seed={event.id}
          startsAt={event.starts_at}
          timezone={event.timezone}
          imageUrl={event.cover_image_url}
          aspect="aspect-[4/3] md:aspect-[4/5]"
        />
        <div className="space-y-5">
          <header className="space-y-3">
            {event.category && <Badge>{event.category}</Badge>}
            <h1 className="font-display text-display text-ink">{event.title}</h1>
          </header>
          {event.status === "cancelled" && <Alert kind="error">{t("cancelled")}</Alert>}
          <dl className="grid gap-x-6 gap-y-4 border-t border-line pt-5 sm:grid-cols-2">
            <div>
              <dt className="text-sm font-semibold text-ink-muted">{t("when")}</dt>
              <dd className="font-semibold text-ink">
                {when(event.starts_at, event.timezone)} – {when(event.ends_at, event.timezone)}
                <span className="block text-sm font-normal text-ink-muted">{event.timezone}</span>
              </dd>
            </div>
            {venue && (
              <div>
                <dt className="text-sm font-semibold text-ink-muted">{t("where")}</dt>
                <dd className="font-semibold text-ink">
                  {venue.name}
                  <span className="block text-sm font-normal text-ink-muted">
                    {[venue.address_line1, venue.city].filter(Boolean).join(", ")}
                  </span>
                </dd>
              </div>
            )}
            <div className="sm:col-span-2">
              <dt className="text-sm font-semibold text-ink-muted">{t("organizer")}</dt>
              <dd className="font-semibold text-ink">
                {event.organizer.display_name}
                <a href={`mailto:${event.organizer.contact_email}`} className={`block w-fit text-sm ${LINK}`}>
                  {event.organizer.contact_email}
                </a>
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="space-y-6">
          {event.description && (
            <div className="max-w-[65ch] whitespace-pre-line text-lg leading-relaxed text-ink">{event.description}</div>
          )}
          {event.refund_policy && (
            <section aria-labelledby="refund-policy" className="max-w-[65ch] rounded-card border border-line bg-surface p-5">
              <h2 id="refund-policy" className="mb-1 font-semibold text-ink">
                {t("refundPolicy")}
              </h2>
              <p className="whitespace-pre-line text-ink-muted">{event.refund_policy}</p>
            </section>
          )}
        </div>

        <aside
          aria-labelledby="tickets-heading"
          className="h-fit space-y-4 rounded-card border border-line bg-surface p-5 lg:sticky lg:top-24"
        >
          <h2 id="tickets-heading" className={SECTION_TITLE}>
            {t("tickets")}
          </h2>
          {ticketSlot ?? (
            <ul className="space-y-3">
              {event.ticket_types.length === 0 && <li className="text-ink-muted">{t("noTickets")}</li>}
              {event.ticket_types.map((tt) => (
                <li key={tt.id} className="border-t border-line pt-3 first:border-t-0 first:pt-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-semibold text-ink">{tt.name}</span>
                    <PriceTag>{tt.is_free ? t("free") : money(tt.price_kzt)}</PriceTag>
                  </div>
                  <p className="text-sm text-ink-muted">
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
      </div>
    </article>
  );
}
