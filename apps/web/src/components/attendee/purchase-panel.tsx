"use client";

import type { Schemas } from "@biletflow/api-types";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import type { PublicEvent } from "@/components/event-view";
import { Alert, Button, Field } from "@/components/ui";
import { usePathname, useRouter } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useMoney } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

type Attendee = Schemas["AttendeeInput"];

/** Ticket selection, then attendee details, then the order (SRS 4.4, 4.6). Totals shown
 * here are a preview; the server computes the real amounts. */
export function PurchasePanel({ event }: { event: PublicEvent }) {
  const t = useTranslations();
  const format = useFormatter();
  const money = useMoney();
  const errorMessage = useErrorMessage();
  const router = useRouter();
  const pathname = usePathname();
  const { status, user } = useAuth();
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  const [step, setStep] = useState<"select" | "attendees">("select");
  const [attendees, setAttendees] = useState<Attendee[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const selected = event.ticket_types.filter((tt) => (quantities[tt.id] ?? 0) > 0);
  const total = selected.reduce((sum, tt) => sum + tt.price_kzt * quantities[tt.id], 0);
  const slots = selected.flatMap((tt) => Array.from({ length: quantities[tt.id] }, () => tt));

  if (event.status === "cancelled") return null;
  if (!event.registration_open) {
    const opensLater = event.registration_opens_at && new Date(event.registration_opens_at) > new Date();
    return (
      <Alert kind="info">
        {opensLater
          ? t("event.view.registrationNotOpen", {
              date: format.dateTime(new Date(event.registration_opens_at!), {
                dateStyle: "medium",
                timeStyle: "short",
                timeZone: event.timezone,
              }),
            })
          : t("purchase.registrationClosed")}
      </Alert>
    );
  }

  function toAttendees() {
    setError(null);
    if (slots.length === 0) {
      setError(new Error("select"));
      return;
    }
    if (status !== "authenticated") {
      router.push({ pathname: "/login", query: { next: pathname } });
      return;
    }
    setAttendees(
      slots.map((_, i) =>
        i === 0 && user ? { full_name: user.full_name, email: user.email } : { full_name: "", email: null },
      ),
    );
    setStep("attendees");
  }

  async function placeOrder(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const order = await unwrap(
        api.POST("/api/v1/orders", {
          body: {
            event_id: event.id,
            items: selected.map((tt) => ({ ticket_type_id: tt.id, quantity: quantities[tt.id] })),
            attendees: attendees.map((a) => ({ ...a, email: a.email || null })),
          },
        }),
      );
      router.push(order.payment_required ? `/checkout/${order.id}` : `/orders/${order.id}`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  const errorText =
    error instanceof Error && error.message === "select" ? t("purchase.selectTickets") : error ? errorMessage(error) : null;

  if (step === "attendees") {
    return (
      <form onSubmit={placeOrder} className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="font-semibold text-gray-900">{t("purchase.attendeesTitle")}</h3>
        <p className="text-sm text-gray-600">{t("purchase.attendeesLead")}</p>
        {errorText && <Alert kind="error">{errorText}</Alert>}
        {slots.map((tt, i) => (
          <fieldset key={i} className="space-y-2 border-t border-gray-100 pt-3">
            <legend className="text-sm font-medium text-gray-900">
              {t("purchase.attendee", { number: i + 1, type: tt.name })}
            </legend>
            <Field
              label={t("purchase.attendeeName")}
              value={attendees[i]?.full_name ?? ""}
              onChange={(e) =>
                setAttendees((prev) => prev.map((a, j) => (j === i ? { ...a, full_name: e.target.value } : a)))
              }
              required
              maxLength={200}
              autoComplete={i === 0 ? "name" : "off"}
            />
            <Field
              label={`${t("purchase.attendeeEmail")} (${t("common.optional")})`}
              type="email"
              value={attendees[i]?.email ?? ""}
              onChange={(e) =>
                setAttendees((prev) => prev.map((a, j) => (j === i ? { ...a, email: e.target.value } : a)))
              }
            />
          </fieldset>
        ))}
        <div className="flex items-center justify-between border-t border-gray-100 pt-3 font-semibold text-gray-900">
          <span>{t("purchase.total")}</span>
          <span>{total === 0 ? t("event.view.free") : money(total)}</span>
        </div>
        <div className="flex flex-col gap-2">
          <Button type="submit" disabled={busy}>
            {total === 0 ? t("purchase.placeOrder") : t("purchase.reserve")}
          </Button>
          <Button type="button" variant="secondary" onClick={() => setStep("select")}>
            {t("purchase.back")}
          </Button>
        </div>
      </form>
    );
  }

  return (
    <div className="space-y-3">
      {event.ticket_types.length === 0 && <p className="text-gray-600">{t("event.view.noTickets")}</p>}
      {event.ticket_types.map((tt) => {
        const paidBlocked = !tt.is_free && !event.paid_sales_enabled;
        const max = Math.min(tt.max_per_order, tt.quantity_available);
        const disabled = !tt.on_sale || max === 0 || paidBlocked;
        return (
          <div key={tt.id} className="rounded-md border border-gray-200 bg-white p-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-medium text-gray-900">{tt.name}</span>
              <span className="font-semibold text-gray-900">{tt.is_free ? t("event.view.free") : money(tt.price_kzt)}</span>
            </div>
            {tt.description && <p className="text-sm text-gray-600">{tt.description}</p>}
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="text-sm text-gray-600">
                {paidBlocked
                  ? t("event.view.paidNotEnabled")
                  : tt.quantity_available === 0
                    ? t("event.view.soldOut")
                    : !tt.on_sale
                      ? t("event.view.notOnSale")
                      : t("event.view.left", { count: tt.quantity_available })}
              </span>
              <label className="flex items-center gap-2 text-sm">
                <span className="sr-only">{t("purchase.quantity", { name: tt.name })}</span>
                <select
                  value={quantities[tt.id] ?? 0}
                  disabled={disabled}
                  onChange={(e) => setQuantities((q) => ({ ...q, [tt.id]: Number(e.target.value) }))}
                  className="rounded-md border border-gray-300 bg-white px-2 py-1 disabled:opacity-50"
                >
                  {Array.from({ length: (disabled ? 0 : max) + 1 }, (_, n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        );
      })}
      {errorText && <Alert kind="error">{errorText}</Alert>}
      <div className="flex items-center justify-between font-semibold text-gray-900">
        <span>{t("purchase.total")}</span>
        <span>{total === 0 ? t("event.view.free") : money(total)}</span>
      </div>
      <Button className="w-full" onClick={toAttendees}>
        {status === "authenticated" ? t("purchase.continue") : t("purchase.signInToContinue")}
      </Button>
    </div>
  );
}
