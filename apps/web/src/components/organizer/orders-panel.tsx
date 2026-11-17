"use client";

import type { Schemas } from "@biletflow/api-types";
import { useFormatter, useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { Alert, Button, DemoBadge, Field, Select } from "@/components/ui";
import { api, ApiError, unwrap } from "@/lib/api";
import { newIdempotencyKey, useMoney } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

import { useOrganizerEvent } from "./event-shell";

type Order = Schemas["OrganizerOrderRead"];
type OrderStatus = Schemas["OrderStatus"];

const STATUSES: OrderStatus[] = ["confirmed", "awaiting_payment", "refunded", "cancelled", "failed", "expired"];

/** The organizer's orders (SRS 4.9): refund paid orders in full (DEMO) or cancel free
 * registrations, each behind a confirmation. */
export function OrdersPanel() {
  const t = useTranslations("organizer.orders");
  const to = useTranslations("order.status");
  const tc = useTranslations("common");
  const money = useMoney();
  const format = useFormatter();
  const errorMessage = useErrorMessage();
  const { event } = useOrganizerEvent();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<OrderStatus | "">("");
  const [result, setResult] = useState<{ key: string; list?: Schemas["OrganizerOrderList"]; error?: unknown } | null>(null);
  const [confirming, setConfirming] = useState<{ order: Order; action: "refund" | "cancel" } | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  // One key per refund attempt, reused if the network fails, so a retry never refunds twice.
  const refundKey = useRef<string | null>(null);
  const key = `${event.id}|${query.trim()}|${status}|${reload}`;

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      unwrap(
        api.GET("/api/v1/organizer/events/{event_id}/orders", {
          params: { path: { event_id: event.id }, query: { q: query.trim() || null, status: status || null } },
        }),
      )
        .then((list) => active && setResult({ key, list }))
        .catch((error: unknown) => active && setResult({ key, error }));
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [key, event.id, query, status]);

  const open = useCallback((order: Order, action: "refund" | "cancel") => {
    refundKey.current = null;
    setActionError(null);
    setNotice(null);
    setConfirming({ order, action });
  }, []);

  async function confirm(reason: string | null) {
    if (!confirming) return;
    const { order, action } = confirming;
    setBusy(true);
    setActionError(null);
    try {
      if (action === "refund") {
        refundKey.current = refundKey.current ?? newIdempotencyKey();
        await unwrap(
          api.POST("/api/v1/organizer/events/{event_id}/orders/{order_id}/refund", {
            params: {
              path: { event_id: event.id, order_id: order.id },
              header: { "Idempotency-Key": refundKey.current },
            },
            body: { reason },
          }),
        );
        setNotice(t("refundedNotice", { reference: order.reference }));
      } else {
        await unwrap(
          api.POST("/api/v1/organizer/events/{event_id}/orders/{order_id}/cancel", {
            params: { path: { event_id: event.id, order_id: order.id } },
            body: { reason },
          }),
        );
        setNotice(t("cancelledNotice", { reference: order.reference }));
      }
      refundKey.current = null;
      setConfirming(null);
      setReload((n) => n + 1);
    } catch (err) {
      if (!(err instanceof ApiError && err.code === "network")) refundKey.current = null;
      setActionError(err);
    } finally {
      setBusy(false);
    }
  }

  const list = result?.list;
  return (
    <div className="space-y-4">
      <p className="flex flex-wrap items-center gap-2 text-gray-600">
        <DemoBadge label={tc("demo")} /> {t("lead")}
      </p>
      <div className="grid gap-3 sm:grid-cols-[1fr_12rem]">
        <Field type="search" label={t("search")} hint={t("searchHint")} value={query} onChange={(e) => setQuery(e.target.value)} maxLength={200} />
        <Select
          label={t("statusFilter")}
          value={status}
          onChange={(e) => setStatus(e.target.value as OrderStatus | "")}
          options={[{ value: "", label: t("all") }, ...STATUSES.map((s) => ({ value: s, label: to(s) }))]}
        />
      </div>
      {notice && <Alert kind="success">{notice}</Alert>}
      {result?.error ? <Alert kind="error">{errorMessage(result.error)}</Alert> : null}
      {!result && <p className="text-gray-600">{tc("loading")}</p>}
      {confirming && (
        <div className="space-y-2">
          {actionError ? <Alert kind="error">{errorMessage(actionError)}</Alert> : null}
          <ConfirmDialog
            title={
              confirming.action === "refund"
                ? t("refundTitle", { reference: confirming.order.reference })
                : t("cancelTitle", { reference: confirming.order.reference })
            }
            text={
              confirming.action === "refund"
                ? t("refundText", { buyer: confirming.order.buyer_name, amount: money(confirming.order.total_kzt) })
                : t("cancelText", { buyer: confirming.order.buyer_name })
            }
            reasonLabel={t("reason")}
            confirmLabel={confirming.action === "refund" ? t("confirmRefund") : t("confirmCancel")}
            cancelLabel={t("keep")}
            busy={busy}
            onConfirm={(reason) => void confirm(reason)}
            onCancel={() => setConfirming(null)}
          />
        </div>
      )}
      {list && list.orders.length === 0 && <p className="text-gray-600">{t("empty")}</p>}
      {list && list.orders.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-left text-gray-700">
              <tr>
                {(["reference", "buyer", "tickets", "total", "status", "placed", "actions"] as const).map((col) => (
                  <th key={col} scope="col" className="px-3 py-2 font-semibold">
                    {t(`col.${col}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 text-gray-900">
              {list.orders.map((o) => (
                <tr key={o.id}>
                  <th scope="row" className="px-3 py-2 text-left font-mono font-medium">
                    {o.reference}
                  </th>
                  <td className="px-3 py-2">
                    {o.buyer_name}
                    <span className="block text-xs text-gray-600">{o.buyer_email}</span>
                  </td>
                  <td className="px-3 py-2">{o.tickets}</td>
                  <td className="px-3 py-2">
                    {o.total_kzt === 0 ? "—" : money(o.total_kzt)}
                    {o.refunded_kzt > 0 && (
                      <span className="block text-xs text-gray-600">{t("refundedAmount", { amount: money(o.refunded_kzt) })}</span>
                    )}
                    {o.promo_code && <span className="block font-mono text-xs text-gray-600">{o.promo_code}</span>}
                  </td>
                  <td className="px-3 py-2">{to(o.status)}</td>
                  <td className="px-3 py-2">
                    {format.dateTime(new Date(o.created_at), { dateStyle: "short", timeStyle: "short", timeZone: event.timezone })}
                  </td>
                  <td className="px-3 py-2">
                    {o.can_refund && (
                      <Button variant="secondary" onClick={() => open(o, "refund")}>
                        {t("refund")}
                      </Button>
                    )}
                    {o.can_cancel && (
                      <Button variant="secondary" onClick={() => open(o, "cancel")}>
                        {t("cancel")}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {list?.truncated && <p className="text-sm text-gray-600">{t("truncated")}</p>}
    </div>
  );
}
