"use client";

import type { Schemas } from "@biletflow/api-types";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert, buttonClass, EmptyState, PageTitle } from "@/components/ui";
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
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <PageTitle className="mb-0">{t("organizer.events.title")}</PageTitle>
        <Link
          href="/organizer/events/new"
          className={buttonClass("primary")}
        >
          {t("organizer.events.new")}
        </Link>
      </div>
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      {events === null && !error && <p className="text-ink-muted">{t("common.loading")}</p>}
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
                    className={`inline-flex min-h-10 items-center rounded-full border px-4 font-semibold ${phase === p ? "border-ink bg-ink text-surface" : "border-line-strong bg-surface text-ink hover:bg-paper"}`}
                  >
                    {p === "all" ? t("organizer.events.all") : t(`event.phase.${p}`)} ({count})
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      )}
      {(events?.length === 0 || shown?.length === 0) && <EmptyState>{t("organizer.events.empty")}</EmptyState>}
      {shown && shown.length > 0 && (
        <ul className="divide-y divide-line rounded-card border border-line bg-surface">
          {shown.map((event) => (
            <li key={event.id} className="flex flex-wrap items-center gap-4 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-ink">{event.title}</p>
                <p className="text-sm text-ink-muted">
                  {format.dateTime(new Date(event.starts_at), {
                    dateStyle: "medium",
                    timeStyle: "short",
                    timeZone: event.timezone,
                  })}
                  {event.venue ? ` · ${event.venue.name}, ${event.venue.city}` : ""}
                </p>
              </div>
              <span className="rounded-full border border-line-strong px-2 py-0.5 text-xs font-medium text-ink">
                {t(`event.phase.${event.phase}`)} · {t(`event.status.${event.status}`)}
              </span>
              <Link
                href={`/organizer/events/${event.id}`}
                className="text-sm font-semibold text-sky-ink underline decoration-1 underline-offset-4 hover:decoration-2"
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
