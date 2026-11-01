"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Alert, Button, Card, DemoBadge, PageTitle } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { api, ApiError, unwrap } from "@/lib/api";
import { newIdempotencyKey, useEventDateTime, useMoney } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

type Order = Schemas["OrderRead"];

/** The DEMO payment step (SRS 4.6). Nothing here collects card data or moves money. */
export function CheckoutPage() {
  const t = useTranslations();
  const money = useMoney();
  const when = useEventDateTime();
  const errorMessage = useErrorMessage();
  const router = useRouter();
  const { orderId } = useParams<{ orderId: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [outcome, setOutcome] = useState<"failed" | "abandoned" | null>(null);
  const [busy, setBusy] = useState(false);
  // Reused if a request fails on the network, so a retry can never charge twice.
  const pendingKey = useRef<string | null>(null);

  useEffect(() => {
    unwrap(api.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: orderId } } }))
      .then((o) => {
        if (o.status === "confirmed") router.replace(`/orders/${o.id}`);
        else setOrder(o);
      })
      .catch(setError);
  }, [orderId, router]);

  async function pay(result: "succeed" | "fail") {
    setBusy(true);
    setError(null);
    const key = pendingKey.current ?? newIdempotencyKey();
    pendingKey.current = key;
    try {
      const paid = await unwrap(
        api.POST("/api/v1/orders/{order_id}/payments", {
          params: { path: { order_id: orderId }, header: { "Idempotency-Key": key } },
          body: { outcome: result },
        }),
      );
      pendingKey.current = null;
      if (paid.order.status === "confirmed") {
        router.replace(`/orders/${orderId}`);
        return;
      }
      setOrder(paid.order);
      setOutcome("failed");
    } catch (err) {
      if (!(err instanceof ApiError && err.code === "network")) pendingKey.current = null;
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function abandon() {
    setBusy(true);
    setError(null);
    try {
      setOrder(await unwrap(api.POST("/api/v1/orders/{order_id}/abandon", { params: { path: { order_id: orderId } } })));
      setOutcome("abandoned");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (!order) {
    return error ? <Alert kind="error">{errorMessage(error)}</Alert> : <p className="text-gray-600">{t("common.loading")}</p>;
  }

  const open = order.status === "awaiting_payment";
  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div className="flex items-center gap-3">
        <PageTitle>{t("checkout.title")}</PageTitle>
        <DemoBadge label={t("common.demo")} />
      </div>
      <Alert kind="demo">{t("checkout.demoBanner")}</Alert>
      <Card className="space-y-3">
        <p className="text-sm text-gray-600">{t("checkout.summary", { reference: order.reference })}</p>
        <h2 className="text-lg font-semibold text-gray-900">{order.event.title}</h2>
        <p className="text-sm text-gray-700">{when(order.event.starts_at, order.event.timezone)}</p>
        <ul className="divide-y divide-gray-100 text-sm">
          {order.items.map((item) => (
            <li key={item.id} className="flex justify-between py-2">
              <span>
                {item.ticket_type_name} × {item.quantity}
              </span>
              <span>{money(item.line_total_kzt)}</span>
            </li>
          ))}
        </ul>
        <div className="flex justify-between border-t border-gray-200 pt-2 font-semibold">
          <span>{t("purchase.total")}</span>
          <span>{money(order.total_kzt)}</span>
        </div>
        {open && order.expires_at && (
          <p className="text-sm text-gray-600">
            {t("checkout.expires", { time: when(order.expires_at, order.event.timezone) })}
          </p>
        )}
      </Card>
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      {outcome === "failed" && <Alert kind="error">{t("checkout.failed")}</Alert>}
      {outcome === "abandoned" && <Alert kind="info">{t("checkout.abandoned")}</Alert>}
      {open ? (
        <div className="flex flex-col gap-2">
          <Button disabled={busy} onClick={() => void pay("succeed")}>
            {busy ? t("checkout.processing") : t("checkout.paySucceed", { amount: money(order.total_kzt) })}
          </Button>
          <Button variant="secondary" disabled={busy} onClick={() => void pay("fail")}>
            {t("checkout.payFail")}
          </Button>
          <Button variant="secondary" disabled={busy} onClick={() => void abandon()}>
            {t("checkout.abandon")}
          </Button>
        </div>
      ) : (
        <Link href={`/events/${order.event.slug}`} className="font-medium text-gray-900 underline">
          {t("checkout.backToEvent")}
        </Link>
      )}
    </div>
  );
}
