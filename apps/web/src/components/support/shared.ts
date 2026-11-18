import type { Schemas } from "@biletflow/api-types";

export const CATEGORIES: Schemas["SupportCategory"][] = [
  "ticket_delivery",
  "payment",
  "refund",
  "event_information",
  "check_in",
  "seating",
  "account",
  "technical",
];

// SRS 4.13: an organizer asks the platform about account, activation, payment or technical issues.
export const ORGANIZER_CATEGORIES: Schemas["SupportCategory"][] = ["account", "payment", "refund", "technical"];

export const STATUSES: Schemas["SupportCaseStatus"][] = ["open", "in_progress", "waiting_for_customer", "resolved"];

export const STATUS_STYLE: Record<Schemas["SupportCaseStatus"], string> = {
  open: "border-blue-300 bg-blue-50 text-blue-900",
  in_progress: "border-amber-400 bg-amber-50 text-amber-950",
  waiting_for_customer: "border-violet-300 bg-violet-50 text-violet-900",
  resolved: "border-green-300 bg-green-50 text-green-900",
};

type Translate = (key: string, values?: Record<string, string>) => string;

/** "Ticket BFT-… · Order BF-… · Event: …", whatever the case is linked to. */
export function contextLine(t: Translate, context: Schemas["CaseContext"]): string {
  const parts: string[] = [];
  if (context.ticket_number) parts.push(t("context.ticket", { number: context.ticket_number }));
  if (context.order_reference) parts.push(t("context.order", { reference: context.order_reference }));
  if (context.event_title) parts.push(t("context.event", { title: context.event_title }));
  return parts.length ? parts.join(" · ") : t("context.none");
}
