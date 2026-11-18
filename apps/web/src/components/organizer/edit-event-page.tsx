"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui";
import { api, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

import { EventForm } from "./event-form";

type Event = Schemas["EventRead"];

export function EditEventPage() {
  const t = useTranslations();
  const errorMessage = useErrorMessage();
  const { eventId } = useParams<{ eventId: string }>();
  const [event, setEvent] = useState<Event | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    unwrap(api.GET("/api/v1/organizer/events/{event_id}", { params: { path: { event_id: eventId } } }))
      .then(setEvent)
      .catch(setError);
  }, [eventId]);

  if (error) return <Alert kind="error">{errorMessage(error)}</Alert>;
  if (!event) return <p className="text-gray-600">{t("common.loading")}</p>;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">{t("event.form.editTitle")}</h1>
        <span className="rounded-full border border-gray-300 px-2 py-0.5 text-xs font-medium text-gray-800">
          {t(`event.status.${event.status}`)}
        </span>
      </div>
      <EventForm
        key={event.updated_at}
        event={event}
        submitLabel={t("common.save")}
        onSubmit={async (input) => {
          setEvent(
            await unwrap(
              api.PATCH("/api/v1/organizer/events/{event_id}", {
                params: { path: { event_id: event.id } },
                body: input,
              }),
            ),
          );
        }}
      />
    </div>
  );
}
