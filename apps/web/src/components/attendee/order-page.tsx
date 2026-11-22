"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { TicketPdfButton } from "@/components/ticket-pdf-button";
import { TicketQr } from "@/components/ticket-qr";
import { TicketCard } from "@/components/ticket-card";
import { Alert, Card, LINK, PageTitle, PriceTag, buttonClass } from "@/components/ui";
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
  if (!order) return <p className="text-ink-muted">{t("common.loading")}</p>;

  const confirmed = order.status === "confirmed";
  return (
    <div className="space-y-6">
      {confirmed ? (
        <div className="space-y-2">
          <h1 className="font-display text-display text-ink">{t("order.confirmedTitle")}</h1>
          <p className="max-w-[65ch] text-lg text-ink-muted">{t("order.confirmedLead")}</p>
        </div>
      ) : (
        <PageTitle>{t("order.reference", { reference: order.reference })}</PageTitle>
      )}
      <Card className="max-w-2xl space-y-3">
        <p className="text-sm text-ink-muted">{t("order.reference", { reference: order.reference })}</p>
        <h2 className="font-display text-2xl text-ink">{order.event.title}</h2>
        <p className="font-semibold text-sky-ink">
          {when(order.event.starts_at, order.event.timezone)}
          {order.event.venue_name ? ` · ${order.event.venue_name}` : ""}
        </p>
        <p className="text-sm text-ink-muted">
          {t("order.statusLabel", { status: t(`order.status.${order.status}`) })}
        </p>
        {order.discount_kzt > 0 && (
          <dl className="space-y-1 text-sm text-ink-muted">
            <div className="flex justify-between">
              <dt>{t("order.subtotal")}</dt>
              <dd>{money(order.subtotal_kzt)}</dd>
            </div>
            <div className="flex justify-between">
              <dt>{t("order.discount", { code: order.promo_code ?? "" })}</dt>
              <dd>−{money(order.discount_kzt)}</dd>
            </div>
          </dl>
        )}
        <p className="border-t-2 border-ink pt-3">
          <PriceTag size="lg">
            {order.total_kzt === 0 ? t("order.free") : `${t("order.total")}: ${money(order.total_kzt)}`}
          </PriceTag>
        </p>
        {order.total_kzt > 0 && confirmed && <p className="rounded-field border-l-4 border-ink bg-demo-soft px-3 py-2 text-sm text-ink">{t("order.demoPaid")}</p>}
        {order.refunded_kzt > 0 && (
          <p className="text-sm font-medium text-ink">{t("order.refunded", { amount: money(order.refunded_kzt) })}</p>
        )}
        {order.status === "cancelled" && order.tickets.length > 0 && (
          <p className="text-sm text-ink">{t("order.cancelledNote")}</p>
        )}
        <Link href={{ pathname: "/support/new", query: { order: order.id } }} className={`block w-fit text-sm ${LINK}`}>
          {t("support.getHelp")}
        </Link>
        {order.payment_required && (
          <Link href={`/checkout/${order.id}`} className={buttonClass("primary")}>
            {t("order.payNow")}
          </Link>
        )}
      </Card>
      {order.tickets.length > 0 && (
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {order.tickets.map((ticket) => (
            <li key={ticket.id}>
              <TicketCard
                qr={<TicketQr ticketId={ticket.id} ticketNumber={ticket.ticket_number} enlargeable={ticket.status === "valid"} />}
                number={ticket.ticket_number}
                details={`${ticket.ticket_type_name} · ${ticket.attendee_name}`}
              >
                <TicketPdfButton ticketId={ticket.id} ticketNumber={ticket.ticket_number} />
              </TicketCard>
            </li>
          ))}
        </ul>
      )}
      {confirmed && (
        <Link href="/tickets" className={buttonClass("primary")}>
          {t("order.viewTickets")}
        </Link>
      )}
    </div>
  );
}
