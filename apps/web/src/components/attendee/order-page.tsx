"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { TicketQr } from "@/components/ticket-qr";
import { Alert, Card, PageTitle } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useEventDateTime, useMoney } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

type Order = Schemas["OrderRead"];

export function OrderPage() {
  const t = useTranslations();
  const money = useMoney();
  const when = useEventDateTime();
  const errorMessage = useErrorMessage();
  const { orderId } = useParams<{ orderId: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    unwrap(api.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: orderId } } }))
      .then(setOrder)
      .catch(setError);
  }, [orderId]);

  if (error) return <Alert kind="error">{errorMessage(error)}</Alert>;
  if (!order) return <p className="text-gray-600">{t("common.loading")}</p>;

  const confirmed = order.status === "confirmed";
  return (
    <div className="space-y-6">
      {confirmed ? (
        <div className="space-y-2">
          <PageTitle>{t("order.confirmedTitle")}</PageTitle>
          <p className="-mt-4 text-gray-700">{t("order.confirmedLead")}</p>
        </div>
      ) : (
        <PageTitle>{t("order.reference", { reference: order.reference })}</PageTitle>
      )}
      <Card className="space-y-2">
        <p className="text-sm text-gray-600">{t("order.reference", { reference: order.reference })}</p>
        <h2 className="text-lg font-semibold text-gray-900">{order.event.title}</h2>
        <p className="text-gray-700">
          {when(order.event.starts_at, order.event.timezone)}
          {order.event.venue_name ? ` · ${order.event.venue_name}` : ""}
        </p>
        <p className="text-sm text-gray-700">
          {t("order.statusLabel", { status: t(`order.status.${order.status}`) })}
        </p>
        <p className="font-semibold text-gray-900">
          {order.total_kzt === 0 ? t("order.free") : `${t("order.total")}: ${money(order.total_kzt)}`}
        </p>
        {order.total_kzt > 0 && confirmed && <p className="text-sm text-amber-900">{t("order.demoPaid")}</p>}
        {order.payment_required && (
          <Link href={`/checkout/${order.id}`} className="font-medium text-gray-900 underline">
            {t("order.payNow")}
          </Link>
        )}
      </Card>
      {order.tickets.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2">
          {order.tickets.map((ticket) => (
            <li key={ticket.id}>
              <Card className="flex flex-col items-center gap-3 text-center">
                <TicketQr ticketId={ticket.id} ticketNumber={ticket.ticket_number} />
                <p className="font-mono text-lg font-bold tracking-wider">{ticket.ticket_number}</p>
                <p className="text-sm text-gray-700">
                  {ticket.ticket_type_name} · {ticket.attendee_name}
                </p>
              </Card>
            </li>
          ))}
        </ul>
      )}
      {confirmed && (
        <Link href="/tickets" className="inline-block rounded-md bg-gray-900 px-4 py-2 text-sm font-semibold text-white">
          {t("order.viewTickets")}
        </Link>
      )}
    </div>
  );
}
