"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { EventView, type PublicEvent } from "@/components/event-view";
import { Alert } from "@/components/ui";
import { api, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

import { useOrganizerEvent } from "./event-shell";

export function PreviewPanel() {
  const t = useTranslations();
  const errorMessage = useErrorMessage();
  const { event } = useOrganizerEvent();
  const [preview, setPreview] = useState<PublicEvent | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    unwrap(
      api.GET("/api/v1/organizer/events/{event_id}/preview", { params: { path: { event_id: event.id } } }),
    )
      .then(setPreview)
      .catch(setError);
  }, [event.id, event.updated_at]);

  if (error) return <Alert kind="error">{errorMessage(error)}</Alert>;
  if (!preview) return <p className="text-gray-600">{t("common.loading")}</p>;
  return (
    <div className="space-y-6">
      <Alert kind="info">{t("organizer.preview.banner")}</Alert>
      <div className="rounded-lg border-2 border-dashed border-gray-300 p-4 sm:p-6">
        <EventView event={preview} />
      </div>
    </div>
  );
}
