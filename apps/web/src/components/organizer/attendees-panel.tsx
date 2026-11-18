"use client";

import type { Schemas } from "@biletflow/api-types";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert, EmptyState, Field, Select } from "@/components/ui";
import { api, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

import { useOrganizerEvent } from "./event-shell";

type TicketStatus = Schemas["TicketStatus"];
type AttendeeList = Schemas["OrganizerAttendeeList"];

const STATUSES: TicketStatus[] = ["valid", "checked_in", "cancelled", "refunded"];

/** The organizer's attendee list with live ticket status (SRS 4.4, 4.8). */
export function AttendeesPanel() {
  const t = useTranslations("organizer.attendees");
  const tt = useTranslations("tickets.status");
  const tc = useTranslations("common");
  const format = useFormatter();
  const errorMessage = useErrorMessage();
  const { event } = useOrganizerEvent();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<TicketStatus | "">("");
  const [result, setResult] = useState<{ key: string; list?: AttendeeList; error?: unknown } | null>(null);
  const key = `${event.id}|${query.trim()}|${status}`;

  useEffect(() => {
    let active = true;
    // A short pause so typing doesn't send a request per keystroke.
    const timer = setTimeout(() => {
      unwrap(
        api.GET("/api/v1/organizer/events/{event_id}/attendees", {
          params: {
            path: { event_id: event.id },
            query: { q: query.trim() || null, status: status || null },
          },
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

  const list = result?.list;
  return (
    <div className="space-y-4">
      <p className="text-ink-muted">{t("lead")}</p>
      <div className="grid gap-3 sm:grid-cols-[1fr_12rem]">
        <Field
          type="search"
          label={t("search")}
          hint={t("searchHint")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          maxLength={200}
        />
        <Select
          label={t("statusFilter")}
          value={status}
          onChange={(e) => setStatus(e.target.value as TicketStatus | "")}
          options={[{ value: "", label: t("all") }, ...STATUSES.map((s) => ({ value: s, label: tt(s) }))]}
        />
      </div>
      {result?.error ? <Alert kind="error">{errorMessage(result.error)}</Alert> : null}
      {!result && <p className="text-ink-muted">{tc("loading")}</p>}
      {list && (
        <>
          <p className="text-sm font-medium text-ink" aria-live="polite">
            {t("counts", { registered: list.stats.registered, checkedIn: list.stats.checked_in })}
          </p>
          {list.attendees.length === 0 ? (
            <EmptyState>{t("empty")}</EmptyState>
          ) : (
            <div className="overflow-x-auto rounded-card border border-line bg-surface">
              <table className="min-w-full divide-y divide-line text-sm">
                <thead className="bg-paper text-left text-[0.8125rem] text-ink-muted">
                  <tr>
                    {(["name", "email", "type", "number", "order", "status", "checkedIn"] as const).map((col) => (
                      <th key={col} scope="col" className="px-3 py-2 font-semibold">
                        {t(`col.${col}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line text-ink">
                  {list.attendees.map((a) => (
                    <tr key={a.id}>
                      <th scope="row" className="px-3 py-2 text-left font-medium">
                        {a.attendee_name}
                      </th>
                      <td className="px-3 py-2">{a.attendee_email ?? "—"}</td>
                      <td className="px-3 py-2">{a.ticket_type_name}</td>
                      <td className="px-3 py-2 font-mono">{a.ticket_number}</td>
                      <td className="px-3 py-2 font-mono">{a.order_reference}</td>
                      <td className="px-3 py-2">{tt(a.status)}</td>
                      <td className="px-3 py-2">
                        {a.checked_in_at
                          ? format.dateTime(new Date(a.checked_in_at), {
                              dateStyle: "short",
                              timeStyle: "short",
                              timeZone: event.timezone,
                            })
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {list.truncated && <p className="text-sm text-ink-muted">{t("truncated")}</p>}
        </>
      )}
    </div>
  );
}
