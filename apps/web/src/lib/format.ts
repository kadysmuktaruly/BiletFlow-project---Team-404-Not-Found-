"use client";

import { useFormatter } from "next-intl";

/** Whole-tenge amounts, e.g. "15 000 ₸" (locale-aware). */
export function useMoney(): (amountKzt: number) => string {
  const format = useFormatter();
  return (amount) =>
    format.number(amount, { style: "currency", currency: "KZT", maximumFractionDigits: 0 });
}

/** A date and time shown in the event's own time zone (SRS 7), e.g. "20 Dec 2026, 19:00". */
export function useEventDateTime(): (iso: string, timeZone: string) => string {
  const format = useFormatter();
  return (iso, timeZone) =>
    format.dateTime(new Date(iso), { dateStyle: "medium", timeStyle: "short", timeZone });
}

/** A fresh Idempotency-Key for one payment attempt. */
export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}
