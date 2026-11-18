"use client";

import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { Alert, Button, Card, Field, PageTitle, Select, TextArea } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import { api, ApiError, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

import { CATEGORIES, ORGANIZER_CATEGORIES } from "./shared";

/**
 * Open a support case (SRS 4.13). The event, order or ticket comes from the page the user
 * started on (`?event=`, `?order=`, `?ticket=`); the API checks they're the user's own and
 * fills in the rest. `?kind=organizer` asks the platform instead of an event's organizer.
 */
export function NewCasePage() {
  const t = useTranslations("support");
  const errorMessage = useErrorMessage();
  const router = useRouter();
  const search = useSearchParams();
  const kind = search.get("kind") === "organizer" ? "organizer" : "attendee";
  const context = {
    event_id: search.get("event"),
    order_id: search.get("order"),
    ticket_id: search.get("ticket"),
  };
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const categories = kind === "organizer" ? ORGANIZER_CATEGORIES : CATEGORIES;

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const created = await unwrap(
        api.POST("/api/v1/support/cases", {
          body: {
            kind,
            category: String(f.get("category")) as (typeof categories)[number],
            subject: String(f.get("subject") ?? "").trim(),
            message: String(f.get("message") ?? "").trim(),
            ...context,
          },
        }),
      );
      router.replace(`/support/${created.id}`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  const fields = error instanceof ApiError ? error.fields : {};
  // The most specific link wins; the API derives the rest (order → event, ticket → order).
  const about = context.ticket_id
    ? t("form.aboutTicket")
    : context.order_id
      ? t("form.aboutOrder")
      : context.event_id
        ? t("form.aboutEvent")
        : null;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageTitle>{kind === "organizer" ? t("form.titleOrganizer") : t("form.title")}</PageTitle>
      <Card>
        <form onSubmit={submit} className="space-y-4" noValidate>
          {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
          <p className="text-sm text-gray-700">
            <span className="font-medium">{t("form.context")}:</span>{" "}
            {about ?? (kind === "organizer" ? t("kind.organizer") : t("context.none"))}
          </p>
          <Select
            name="category"
            label={t("category.label")}
            options={categories.map((c) => ({ value: c, label: t(`category.${c}`) }))}
          />
          <Field
            name="subject"
            label={t("form.subject")}
            required
            minLength={3}
            maxLength={300}
            error={fields.subject && errorMessage(error)}
          />
          <TextArea name="message" label={t("form.message")} required maxLength={5000} rows={6} />
          <p className="text-sm text-gray-600">{t("form.noAttachments")}</p>
          <Button type="submit" disabled={busy}>
            {t("form.submit")}
          </Button>
        </form>
      </Card>
    </div>
  );
}
