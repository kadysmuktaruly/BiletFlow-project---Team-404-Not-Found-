"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { AddToCalendar } from "@/components/add-to-calendar";
import { TicketPdfButton } from "@/components/ticket-pdf-button";
import { TicketQr } from "@/components/ticket-qr";
import { TicketCard } from "@/components/ticket-card";
import { Alert, EmptyState, LINK, PageTitle, type BadgeTone } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useEventDateTime } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

type MyTicket = Schemas["MyTicketRead"];

const STATUS_TONE: Record<MyTicket["status"], BadgeTone> = {
  valid: "success",
  checked_in: "info",
  cancelled: "neutral",
  refunded: "promo",
};

export function MyTicketsPage() {
  const t = useTranslations();
  const when = useEventDateTime();
  const errorMessage = useErrorMessage();
  const [tickets, setTickets] = useState<MyTicket[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    unwrap(api.GET("/api/v1/me/tickets")).then(setTickets).catch(setError);
  }, []);

  if (error) return <Alert kind="error">{errorMessage(error)}</Alert>;
  if (!tickets) return <p className="text-ink-muted">{t("common.loading")}</p>;

  const byEvent = new Map<string, MyTicket[]>();
  for (const ticket of tickets) byEvent.set(ticket.event.id, [...(byEvent.get(ticket.event.id) ?? []), ticket]);

  return (
    <div className="space-y-8">
      <PageTitle>{t("tickets.title")}</PageTitle>
      {tickets.length === 0 && (
        <EmptyState>
          {t("tickets.empty")}{" "}
          <Link href="/events" className={LINK}>
            {t("tickets.findEvents")}
          </Link>
        </EmptyState>
      )}
      {[...byEvent.values()].map((group) => {
        const event = group[0].event;
        return (
          <section key={event.id} aria-labelledby={`event-${event.id}`} className="space-y-3">
            <div>
              <h2 id={`event-${event.id}`} className="font-display text-2xl text-ink">
                {event.title}
              </h2>
              <p className="font-semibold text-sky-ink">
                {when(event.starts_at, event.timezone)}
                {event.venue_name ? ` · ${event.venue_name}` : ""}
              </p>
              {group.some((ticket) => ticket.status === "valid") && (
                <div className="mt-2">
                  <AddToCalendar slug={event.slug} title={event.title} />
                </div>
              )}
            </div>
            <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {group.map((ticket) => (
                <li key={ticket.id}>
                  <TicketCard
                    qr={<TicketQr ticketId={ticket.id} ticketNumber={ticket.ticket_number} enlargeable={ticket.status === "valid"} />}
                    number={ticket.ticket_number}
                    status={{ label: t(`tickets.status.${ticket.status}`), tone: STATUS_TONE[ticket.status] }}
                    details={`${ticket.ticket_type_name} · ${ticket.attendee_name}`}
                    note={ticket.status === "valid" && <p className="text-xs text-ink-muted">{t("tickets.showAtDoor")}</p>}
                  >
                    <TicketPdfButton ticketId={ticket.id} ticketNumber={ticket.ticket_number} />
                    <Link href={{ pathname: "/support/new", query: { ticket: ticket.id } }} className={`text-sm ${LINK}`}>
                      {t("support.getHelp")}
                    </Link>
                  </TicketCard>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
