"use client";

import type { Schemas } from "@biletflow/api-types";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert, Badge, EmptyState, PageTitle } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useEventDateTime, useMoney } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

/** The attendee's order history (SRS 4.9 "Attendees shall be able to view their orders"). */
export function MyOrdersPage() {
  const t = useTranslations();
  const format = useFormatter();
  const money = useMoney();
  const when = useEventDateTime();
  const errorMessage = useErrorMessage();
  const [orders, setOrders] = useState<Schemas["OrderRead"][] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    unwrap(api.GET("/api/v1/me/orders"))
      .then((data) => active && setOrders(data))
      .catch((err: unknown) => active && setError(err));
    return () => {
      active = false;
    };
  }, []);

  if (error) return <Alert kind="error">{errorMessage(error)}</Alert>;
  if (!orders) return <p className="text-ink-muted">{t("common.loading")}</p>;
  return (
    <div className="space-y-6">
      <PageTitle>{t("orders.title")}</PageTitle>
      {orders.length === 0 && (
        <EmptyState>
          {t("orders.empty")}{" "}
          <Link href="/events" className="font-semibold text-sky-ink underline decoration-1 underline-offset-4 hover:decoration-2">
            {t("tickets.findEvents")}
          </Link>
        </EmptyState>
      )}
      <ul className="space-y-3">
        {orders.map((o) => (
          <li key={o.id} className="rounded-card border border-line bg-surface p-5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <h2 className="font-display text-xl text-ink">{o.event.title}</h2>
              <Badge tone={o.status === "confirmed" ? "success" : o.status === "awaiting_payment" ? "warning" : "neutral"}>
                {t(`order.status.${o.status}`)}
              </Badge>
            </div>
            <p className="text-sm font-semibold text-sky-ink">{when(o.event.starts_at, o.event.timezone)}</p>
            <p className="mt-1 text-sm text-ink-muted">
              <span className="font-mono">{o.reference}</span>
              {" · "}
              {t("orders.tickets", { count: o.tickets.length || o.items.reduce((n, i) => n + i.quantity, 0) })}
              {" · "}
              {o.total_kzt === 0 ? t("order.free") : money(o.total_kzt)}
              {o.refunded_kzt > 0 && ` · ${t("order.refunded", { amount: money(o.refunded_kzt) })}`}
            </p>
            <p className="text-xs text-ink-muted">
              {t("orders.placed", { date: format.dateTime(new Date(o.created_at), { dateStyle: "medium", timeStyle: "short" }) })}
            </p>
            <Link href={`/orders/${o.id}`} className="mt-2 inline-block text-sm font-semibold text-sky-ink underline decoration-1 underline-offset-4 hover:decoration-2">
              {t("orders.view")}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
