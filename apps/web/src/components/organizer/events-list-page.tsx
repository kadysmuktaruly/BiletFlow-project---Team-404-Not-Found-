"use client";

import type { Schemas } from "@biletflow/api-types";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert, PageTitle } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

type Event = Schemas["EventRead"];
type Phase = Event["phase"];
const PHASES: Phase[] = ["upcoming", "active", "completed", "cancelled"];

export function EventsListPage() {
  const t = useTranslations();
  const format = useFormatter();
  const errorMessage = useErrorMessage();
  const [events, setEvents] = useState<Event[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  // SRS 4.16: Upcoming / Active / Completed / Cancelled views.
  const [phase, setPhase] = useState<Phase | "all">("all");

  useEffect(() => {
    unwrap(api.GET("/api/v1/organizer/events")).then(setEvents).catch(setError);
  }, []);
  const shown = events?.filter((e) => phase === "all" || e.phase === phase) ?? null;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <PageTitle>{t("organizer.events.title")}</PageTitle>
        <Link
          href="/organizer/events/new"
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-700"
        >
          {t("organizer.events.new")}
        </Link>
      </div>
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      {events === null && !error && <p className="text-gray-600">{t("common.loading")}</p>}
      {events && events.length > 0 && (
        <nav aria-label={t("organizer.events.view")} className="mb-4">
          <ul className="flex flex-wrap gap-2 text-sm">
            {(["all", ...PHASES] as const).map((p) => {
              const count = p === "all" ? events.length : events.filter((e) => e.phase === p).length;
              return (
                <li key={p}>
                  <button
                    type="button"
                    aria-pressed={phase === p}
                    onClick={() => setPhase(p)}
                    className={`rounded-full border px-3 py-1 font-medium ${phase === p ? "border-gray-900 bg-gray-900 text-white" : "border-gray-300 bg-white text-gray-900 hover:bg-gray-50"}`}
                  >
                    {p === "all" ? t("organizer.events.all") : t(`event.phase.${p}`)} ({count})
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      )}
      {(events?.length === 0 || shown?.length === 0) && <p className="text-gray-600">{t("organizer.events.empty")}</p>}
      {shown && shown.length > 0 && (
        <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
          {shown.map((event) => (
            <li key={event.id} className="flex flex-wrap items-center gap-4 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-gray-900">{event.title}</p>
                <p className="text-sm text-gray-600">
                  {format.dateTime(new Date(event.starts_at), {
                    dateStyle: "medium",
                    timeStyle: "short",
                    timeZone: event.timezone,
                  })}
                  {event.venue ? ` · ${event.venue.name}, ${event.venue.city}` : ""}
                </p>
              </div>
              <span className="rounded-full border border-gray-300 px-2 py-0.5 text-xs font-medium text-gray-800">
                {t(`event.phase.${event.phase}`)} · {t(`event.status.${event.status}`)}
              </span>
              <Link
                href={`/organizer/events/${event.id}`}
                className="text-sm font-medium text-gray-900 underline"
              >
                {event.phase === "completed" || event.phase === "cancelled" ? t("organizer.events.open") : t("organizer.events.edit")}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
