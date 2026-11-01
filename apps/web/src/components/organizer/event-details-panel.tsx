"use client";

import { useTranslations } from "next-intl";

import { api, unwrap } from "@/lib/api";

import { EventForm } from "./event-form";
import { useOrganizerEvent } from "./event-shell";

export function EventDetailsPanel() {
  const t = useTranslations("common");
  const { event, setEvent } = useOrganizerEvent();
  return (
    <EventForm
      key={event.updated_at}
      event={event}
      submitLabel={t("save")}
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
  );
}
