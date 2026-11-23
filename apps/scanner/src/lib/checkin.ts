import type { Schemas } from "@biletflow/api-types";

import { api, unwrap } from "./api";

/** The five check-in outcomes the door must show (SRS 4.8). */
export const RESULT_STATES = ["valid", "invalid", "cancelled", "refunded", "already_used"] as const;
export type ResultState = (typeof RESULT_STATES)[number];

export type ScanResult = Schemas["ScanResult"];
export type CheckInStats = Schemas["CheckInStats"];
export type CheckInTicket = Schemas["CheckInTicket"];
/** What the result screen shows: a server answer, or a local Campaign QR rejection (no counts). */
export type DoorResult = Omit<ScanResult, "stats"> & { stats: CheckInStats | null };

export function isResultState(value: unknown): value is ResultState {
  return typeof value === "string" && (RESULT_STATES as readonly string[]).includes(value);
}

const ADMISSION_PREFIX = "BFT1.";
const CAMPAIGN_PREFIX = "BFC1.";

/**
 * A Campaign QR (SRS 4.14): `BFC1.<token>` or a link to `/c/BFC1.<token>`. Same rule as the
 * API's `_invalid_reason`. The phone may use this only to *reject*: a Campaign QR never
 * admits anyone, even when the API can't be reached. Admission is always decided by the
 * server.
 */
export function isCampaignQr(payload: string): boolean {
  return payload.includes(CAMPAIGN_PREFIX) && !payload.trim().startsWith(ADMISSION_PREFIX);
}

/** The result shown for a Campaign QR without asking the server. */
export function campaignRejection(): DoorResult {
  return { result: "invalid", reason: "campaign_qr_not_admission", ticket: null, method: null, stats: null };
}

/**
 * Validate a scanned QR on the server and record the check-in (SRS 4.8). The phone never
 * decides a ticket is valid: the API checks the signature and the ticket's live status, and
 * admits each ticket once even if two phones scan it at the same moment.
 */
export function scanTicket(eventId: string, payload: string, deviceLabel?: string): Promise<ScanResult> {
  return unwrap(
    api.POST("/api/v1/checkin/events/{event_id}/scan", {
      params: { path: { event_id: eventId } },
      body: { payload, device_label: deviceLabel ?? null },
    }),
  );
}

/** Check in a ticket found by manual search: the same atomic check-in as a scan. */
export function checkInTicket(eventId: string, ticketId: string): Promise<ScanResult> {
  return unwrap(
    api.POST("/api/v1/checkin/events/{event_id}/tickets/{ticket_id}/check-in", {
      params: { path: { event_id: eventId, ticket_id: ticketId } },
      body: { device_label: null },
    }),
  );
}

/** Undo an accidental check-in. Owners and event admins only; the API enforces it. */
export function undoCheckIn(eventId: string, ticketId: string): Promise<Schemas["UndoResult"]> {
  return unwrap(
    api.POST("/api/v1/checkin/events/{event_id}/tickets/{ticket_id}/undo", {
      params: { path: { event_id: eventId, ticket_id: ticketId } },
      body: { reason: null },
    }),
  );
}

export function fetchStats(eventId: string): Promise<CheckInStats> {
  return unwrap(api.GET("/api/v1/checkin/events/{event_id}/stats", { params: { path: { event_id: eventId } } }));
}

export function searchAttendees(eventId: string, q: string): Promise<Schemas["AttendeeSearchResult"]> {
  return unwrap(
    api.GET("/api/v1/checkin/events/{event_id}/attendees", {
      params: { path: { event_id: eventId }, query: { q: q.trim() || null } },
    }),
  );
}

/** i18n key explaining an `invalid` result, if the server gave a reason. */
export function invalidReasonKey(result: Pick<ScanResult, "result" | "reason">): string | null {
  return result.result === "invalid" && result.reason ? `result.reasons.${result.reason}` : null;
}

/** "14:05" in the event's own time zone, so door staff see the local time. */
export function formatTime(iso: string | null | undefined, timeZone: string | undefined, locale: string): string | null {
  if (!iso) return null;
  try {
    return new Intl.DateTimeFormat(locale, { timeStyle: "short", timeZone }).format(new Date(iso));
  } catch {
    return new Date(iso).toISOString().slice(11, 16);
  }
}
