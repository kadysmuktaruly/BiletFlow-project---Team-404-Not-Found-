"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { EventCard } from "@/components/event-card";
import { Alert, Button, EmptyState, PageTitle } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useEventDateTime, useMoney } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

type EventList = Schemas["PublicEventList"];

export function EventsListPage() {
  const t = useTranslations();
  const money = useMoney();
  const when = useEventDateTime();
  const errorMessage = useErrorMessage();
  const router = useRouter();
  const q = useSearchParams().get("q") ?? "";
  const [list, setList] = useState<EventList | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    unwrap(api.GET("/api/v1/events", { params: { query: { q: q || undefined, limit: 50 } } }))
      .then(setList)
      .catch(setError);
  }, [q]);

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <PageTitle>{t("events.title")}</PageTitle>
        <form
          role="search"
          className="flex w-full gap-2 sm:mb-6 sm:max-w-md"
          onSubmit={(e) => {
            e.preventDefault();
            const value = String(new FormData(e.currentTarget).get("q") ?? "").trim();
            router.replace({ pathname: "/events", query: value ? { q: value } : {} });
          }}
        >
          <label className="sr-only" htmlFor="event-search">
            {t("events.search")}
          </label>
          <input
            id="event-search"
            name="q"
            type="search"
            defaultValue={q}
            placeholder={t("events.search")}
            className="h-11 min-w-0 flex-1 rounded-full border border-line-strong bg-surface px-4 text-ink hover:border-ink-muted"
          />
          <Button type="submit">{t("events.searchButton")}</Button>
        </form>
      </div>
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      {list === null && !error && <p className="text-ink-muted">{t("common.loading")}</p>}
      {list?.items.length === 0 && <EmptyState>{t("events.empty")}</EmptyState>}
      <ul className="grid gap-x-6 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
        {list?.items.map((event) => {
          const prices = event.ticket_types.map((tt) => tt.price_kzt);
          const lowest = prices.length ? Math.min(...prices) : null;
          return (
            <li key={event.id}>
              <EventCard
                href={`/events/${event.slug}`}
                seed={event.id}
                title={event.title}
                startsAt={event.starts_at}
                timezone={event.timezone}
                when={when(event.starts_at, event.timezone)}
                venue={event.venue ? `${event.venue.name}, ${event.venue.city}` : null}
                imageUrl={event.cover_image_url}
                price={
                  lowest === null ? null : lowest === 0 ? t("events.freeEntry") : t("events.from", { price: money(lowest) })
                }
              />
            </li>
          );
        })}
      </ul>
    </div>
  );
}
