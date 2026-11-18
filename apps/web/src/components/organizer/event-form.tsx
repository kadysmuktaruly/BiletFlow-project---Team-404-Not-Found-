"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Alert, Button, Card, Field, Select, TextArea } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

type Event = Schemas["EventRead"];
export type EventInput = Schemas["EventCreate"];

// Kazakhstan's zones first. Since March 2024 they all share UTC+5, but the IANA names stay
// distinct, and organizers may run events abroad.
const TIMEZONES = [
  "Asia/Almaty",
  "Asia/Qostanay",
  "Asia/Qyzylorda",
  "Asia/Aqtobe",
  "Asia/Aqtau",
  "Asia/Atyrau",
  "Asia/Oral",
  "Asia/Tashkent",
  "Asia/Bishkek",
  "Europe/Moscow",
  "Europe/Istanbul",
  "UTC",
];

const blankToNull = (v: FormDataEntryValue | null) => (v && String(v).trim() ? String(v) : null);

export function EventForm({
  event,
  submitLabel,
  onSubmit,
}: {
  event?: Event;
  submitLabel: string;
  onSubmit: (input: EventInput) => Promise<void>;
}) {
  const t = useTranslations("event.form");
  const tc = useTranslations("common");
  const errorMessage = useErrorMessage();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const fields = error instanceof ApiError ? error.fields : {};
  const fieldError = (name: string) => (fields[name] ? errorMessage(error) : undefined);

  async function handle(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await onSubmit({
        title: String(f.get("title")),
        description: blankToNull(f.get("description")),
        category: blankToNull(f.get("category")),
        cover_image_url: blankToNull(f.get("cover_image_url")),
        venue: {
          name: String(f.get("venue_name")),
          address_line1: String(f.get("address_line1")),
          city: String(f.get("city")),
        },
        // datetime-local values carry no offset; the API reads them in `timezone`.
        starts_at: String(f.get("starts_at")),
        ends_at: String(f.get("ends_at")),
        timezone: String(f.get("timezone")),
      });
      setSaved(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handle} className="space-y-6" noValidate>
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      <Card className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">{t("details")}</h2>
        <Field
          name="title"
          label={t("title")}
          defaultValue={event?.title}
          required
          maxLength={300}
          error={fieldError("title")}
        />
        <TextArea
          name="description"
          label={`${t("description")} (${tc("optional")})`}
          defaultValue={event?.description ?? ""}
          rows={6}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            name="category"
            label={`${t("category")} (${tc("optional")})`}
            defaultValue={event?.category ?? ""}
            maxLength={100}
          />
          <Field
            name="cover_image_url"
            type="url"
            label={`${t("coverImage")} (${tc("optional")})`}
            defaultValue={event?.cover_image_url ?? ""}
            placeholder="https://"
            error={fieldError("cover_image_url")}
          />
        </div>
      </Card>

      <Card className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">{t("venue")}</h2>
        <Field
          name="venue_name"
          label={t("venueName")}
          defaultValue={event?.venue?.name}
          required
          error={fieldError("name")}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            name="address_line1"
            label={t("address")}
            defaultValue={event?.venue?.address_line1}
            required
            error={fieldError("address_line1")}
          />
          <Field
            name="city"
            label={t("city")}
            defaultValue={event?.venue?.city}
            required
            error={fieldError("city")}
          />
        </div>
      </Card>

      <Card className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">{t("when")}</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field
            name="starts_at"
            type="datetime-local"
            label={t("startsAt")}
            defaultValue={event?.starts_at_local}
            required
            error={fieldError("starts_at")}
          />
          <Field
            name="ends_at"
            type="datetime-local"
            label={t("endsAt")}
            defaultValue={event?.ends_at_local}
            required
            error={fieldError("ends_at")}
          />
          <Select
            name="timezone"
            label={t("timezone")}
            hint={t("timezoneHint")}
            defaultValue={event?.timezone ?? "Asia/Almaty"}
            options={TIMEZONES.map((tz) => ({ value: tz, label: tz }))}
          />
        </div>
      </Card>

      <div className="flex items-center gap-4">
        <Button type="submit" disabled={busy}>
          {busy ? tc("saving") : submitLabel}
        </Button>
        {saved && <span className="text-sm text-green-800">{tc("saved")}</span>}
      </div>
    </form>
  );
}
