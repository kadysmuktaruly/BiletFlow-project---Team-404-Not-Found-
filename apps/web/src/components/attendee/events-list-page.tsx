"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert, Button, PageTitle } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
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
    <div className="space-y-6">
      <PageTitle>{t("events.title")}</PageTitle>
      <form
        role="search"
        className="flex gap-2"
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
          className="w-full max-w-md rounded-md border border-gray-300 px-3 py-2"
        />
        <Button type="submit" variant="secondary">
          {t("events.searchButton")}
        </Button>
      </form>
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      {list === null && !error && <p className="text-gray-600">{t("common.loading")}</p>}
      {list?.items.length === 0 && <p className="text-gray-600">{t("events.empty")}</p>}
      <ul className="grid gap-4 sm:grid-cols-2">
        {list?.items.map((event) => {
          const prices = event.ticket_types.map((tt) => tt.price_kzt);
          const lowest = prices.length ? Math.min(...prices) : null;
          return (
            <li key={event.id}>
              <Link
                href={`/events/${event.slug}`}
                className="block h-full rounded-lg border border-gray-200 bg-white p-5 shadow-sm hover:border-gray-400 focus-visible:ring-2 focus-visible:ring-gray-900"
              >
                <p className="text-sm text-gray-600">{when(event.starts_at, event.timezone)}</p>
                <h2 className="mt-1 text-lg font-semibold text-gray-900">{event.title}</h2>
                {event.venue && (
                  <p className="text-sm text-gray-700">
                    {event.venue.name}, {event.venue.city}
                  </p>
                )}
                {lowest !== null && (
                  <p className="mt-3 text-sm font-semibold text-gray-900">
                    {lowest === 0 ? t("events.freeEntry") : t("events.from", { price: money(lowest) })}
                  </p>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
