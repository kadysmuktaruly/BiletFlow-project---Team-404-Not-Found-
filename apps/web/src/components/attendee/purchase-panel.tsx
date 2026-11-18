"use client";

import type { Schemas } from "@biletflow/api-types";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import type { PublicEvent } from "@/components/event-view";
import { Alert, Button, Field, INLINE_SELECT, LINK, PriceTag } from "@/components/ui";
import { usePathname, useRouter } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useMoney } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

type Attendee = Schemas["AttendeeInput"];
type PromoQuote = Schemas["PromoQuote"];

/** Ticket selection, then attendee details, then the order (SRS 4.4, 4.6). Totals shown
 * here are a preview; the server computes the real amounts, discounts included (SRS 4.14).
 * `initialPromo` comes from a Campaign QR link, already checked by the server. */
export function PurchasePanel({
  event,
  initialPromo = null,
  campaignRejection = null,
}: {
  event: PublicEvent;
  initialPromo?: string | null;
  campaignRejection?: string | null;
}) {
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
  const [promoInput, setPromoInput] = useState(initialPromo ?? "");
  const [promoCode, setPromoCode] = useState<string | null>(initialPromo);
  // Each server answer remembers which code and selection it was for, so a stale answer is
  // never shown against a changed selection.
  const [promoResult, setPromoResult] = useState<{ key: string; quote?: PromoQuote; error?: unknown } | null>(null);

  const selected = event.ticket_types.filter((tt) => (quantities[tt.id] ?? 0) > 0);
  const subtotal = selected.reduce((sum, tt) => sum + tt.price_kzt * quantities[tt.id], 0);
  const slots = selected.flatMap((tt) => Array.from({ length: quantities[tt.id] }, () => tt));
  const items = selected.map((tt) => ({ ticket_type_id: tt.id, quantity: quantities[tt.id] }));
  const itemsJson = JSON.stringify(items);
  const promoKey = promoCode && items.length > 0 ? `${promoCode}|${itemsJson}` : null;
  const current = promoResult && promoResult.key === promoKey ? promoResult : null;
  const quote = current?.quote ?? null;
  const promoError = current?.error ?? null;
  const checkingPromo = promoKey !== null && current === null;
  const total = quote ? quote.total_kzt : subtotal;

  useEffect(() => {
    if (!promoKey || !promoCode) return;
    let active = true;
    unwrap(
      api.POST("/api/v1/promo/validate", {
        body: { event_id: event.id, code: promoCode, items: JSON.parse(itemsJson) as typeof items },
      }),
    )
      .then((q) => active && setPromoResult({ key: promoKey, quote: q }))
      .catch((err: unknown) => active && setPromoResult({ key: promoKey, error: err }));
    return () => {
      active = false;
    };
    // `itemsJson` is part of `promoKey`; listing both keeps the lint rule exact.
  }, [promoKey, promoCode, itemsJson, event.id]);

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
            items,
            attendees: attendees.map((a) => ({ ...a, email: a.email || null })),
            // Only a code the server accepted for this selection; checkout checks it again.
            promo_code: quote ? quote.code : null,
          },
        }),
      );
      router.push(order.payment_required ? `/checkout/${order.id}` : `/orders/${order.id}`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  const totals = (
    <div className="space-y-2 border-t-2 border-ink pt-4">
      {quote && quote.discount_kzt > 0 && (
        <dl className="space-y-1 text-sm text-ink-muted">
          <div className="flex justify-between">
            <dt>{t("purchase.subtotal")}</dt>
            <dd>{money(quote.subtotal_kzt)}</dd>
          </div>
          <div className="flex justify-between">
            <dt>{t("purchase.discount", { code: quote.code })}</dt>
            <dd>−{money(quote.discount_kzt)}</dd>
          </div>
        </dl>
      )}
      <div className="flex items-baseline justify-between gap-3 text-ink">
        <span className="font-semibold">{t("purchase.total")}</span>
        <PriceTag size="lg">{total === 0 ? t("event.view.free") : money(total)}</PriceTag>
      </div>
    </div>
  );

  const promoBox = (
    <div className="space-y-2">
      {campaignRejection && !promoCode && (
        <Alert kind="info">
          {t("purchase.campaignRejected", {
            reason: t.has(`errors.${campaignRejection}`) ? t(`errors.${campaignRejection}`) : t("errors.generic"),
          })}
        </Alert>
      )}
      {promoCode ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-field bg-info-soft px-3 py-2.5 text-sm" aria-live="polite">
          <span className="font-semibold text-ink">
            {checkingPromo
              ? t("purchase.promoChecking")
              : quote
                ? t("purchase.promoApplied", { code: quote.code, amount: money(quote.discount_kzt) })
                : items.length === 0
                  ? t("purchase.promoPending", { code: promoCode })
                  : null}
          </span>
          <button
            type="button"
            className={LINK}
            onClick={() => {
              setPromoCode(null);
              setPromoInput("");
            }}
          >
            {t("purchase.promoRemove")}
          </button>
          {promoError ? (
            <div className="w-full">
              <Alert kind="error">{errorMessage(promoError)}</Alert>
            </div>
          ) : null}
        </div>
      ) : (
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            const code = promoInput.trim();
            if (code) setPromoCode(code);
          }}
        >
          <Field
            className="flex-1"
            label={t("purchase.promoLabel")}
            value={promoInput}
            onChange={(e) => setPromoInput(e.target.value)}
            maxLength={40}
            autoComplete="off"
            autoCapitalize="characters"
          />
          <Button type="submit" variant="secondary" disabled={!promoInput.trim()}>
            {t("purchase.promoApply")}
          </Button>
        </form>
      )}
    </div>
  );

  const errorText =
    error instanceof Error && error.message === "select" ? t("purchase.selectTickets") : error ? errorMessage(error) : null;

  if (step === "attendees") {
    return (
      <form onSubmit={placeOrder} className="space-y-4">
        <h3 className="text-lg font-bold text-ink">{t("purchase.attendeesTitle")}</h3>
        <p className="text-sm text-ink-muted">{t("purchase.attendeesLead")}</p>
        {errorText && <Alert kind="error">{errorText}</Alert>}
        {slots.map((tt, i) => (
          <fieldset key={i} className="space-y-3 rounded-field border border-line p-4">
            <legend className="px-1 text-sm font-semibold text-ink">
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
        {totals}
        <div className="flex flex-col gap-2">
          <Button type="submit" disabled={busy} className="min-h-12 text-base">
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
      {event.ticket_types.length === 0 && <p className="text-ink-muted">{t("event.view.noTickets")}</p>}
      {event.ticket_types.map((tt) => {
        const paidBlocked = !tt.is_free && !event.paid_sales_enabled;
        const max = Math.min(tt.max_per_order, tt.quantity_available);
        const disabled = !tt.on_sale || max === 0 || paidBlocked;
        return (
          <div key={tt.id} className="border-b border-line pb-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-semibold text-ink">{tt.name}</span>
              <PriceTag>{tt.is_free ? t("event.view.free") : money(tt.price_kzt)}</PriceTag>
            </div>
            {tt.description && <p className="text-sm text-ink-muted">{tt.description}</p>}
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="text-sm text-ink-muted">
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
                  className={`${INLINE_SELECT} w-16`}
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
      {promoBox}
      {errorText && <Alert kind="error">{errorText}</Alert>}
      {totals}
      <Button className="min-h-12 w-full text-base" onClick={toAttendees}>
        {status === "authenticated" ? t("purchase.continue") : t("purchase.signInToContinue")}
      </Button>
    </div>
  );
}
