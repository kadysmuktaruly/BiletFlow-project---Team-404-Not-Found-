"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { TicketQr } from "@/components/ticket-qr";
import { Alert, PageTitle } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useEventDateTime } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

type MyTicket = Schemas["MyTicketRead"];

const STATUS_STYLE: Record<MyTicket["status"], string> = {
  valid: "bg-green-100 text-green-900",
  checked_in: "bg-blue-100 text-blue-900",
  cancelled: "bg-gray-200 text-gray-900",
  refunded: "bg-purple-100 text-purple-900",
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
  if (!tickets) return <p className="text-gray-600">{t("common.loading")}</p>;

  const byEvent = new Map<string, MyTicket[]>();
  for (const ticket of tickets) byEvent.set(ticket.event.id, [...(byEvent.get(ticket.event.id) ?? []), ticket]);

  return (
    <div className="space-y-8">
      <PageTitle>{t("tickets.title")}</PageTitle>
      {tickets.length === 0 && (
        <p className="text-gray-600">
          {t("tickets.empty")}{" "}
          <Link href="/events" className="font-medium text-gray-900 underline">
            {t("tickets.findEvents")}
          </Link>
        </p>
      )}
      {[...byEvent.values()].map((group) => {
        const event = group[0].event;
        return (
          <section key={event.id} aria-labelledby={`event-${event.id}`} className="space-y-3">
            <div>
              <h2 id={`event-${event.id}`} className="text-xl font-semibold text-gray-900">
                {event.title}
              </h2>
              <p className="text-gray-700">
                {when(event.starts_at, event.timezone)}
                {event.venue_name ? ` · ${event.venue_name}` : ""}
              </p>
            </div>
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {group.map((ticket) => (
                <li key={ticket.id} className="flex flex-col items-center gap-2 rounded-lg border border-gray-200 bg-white p-4 text-center">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[ticket.status]}`}>
                    {t(`tickets.status.${ticket.status}`)}
                  </span>
                  <TicketQr ticketId={ticket.id} ticketNumber={ticket.ticket_number} />
                  <p className="font-mono text-lg font-bold tracking-wider">{ticket.ticket_number}</p>
                  <p className="text-sm text-gray-700">
                    {ticket.ticket_type_name} · {ticket.attendee_name}
                  </p>
                  {ticket.status === "valid" && <p className="text-xs text-gray-600">{t("tickets.showAtDoor")}</p>}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
