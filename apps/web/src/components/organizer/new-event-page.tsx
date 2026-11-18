"use client";

import { useTranslations } from "next-intl";

import { PageTitle } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";

import { EventForm } from "./event-form";

export function NewEventPage() {
  const t = useTranslations("event.form");
  const router = useRouter();
  return (
    <div>
      <PageTitle>{t("newTitle")}</PageTitle>
      <p className="-mt-4 mb-6 text-gray-600">{t("draftNotice")}</p>
      <EventForm
        submitLabel={t("createDraft")}
        onSubmit={async (input) => {
          const event = await unwrap(api.POST("/api/v1/organizer/events", { body: input }));
          router.replace(`/organizer/events/${event.id}`);
        }}
      />
    </div>
  );
}
