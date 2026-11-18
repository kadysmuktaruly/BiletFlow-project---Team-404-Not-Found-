"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Alert, Button, Select, TextArea } from "@/components/ui";
import { api, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

const REASONS: Schemas["EventReportReason"][] = ["fraud", "misleading", "inappropriate", "spam", "other"];

/** "Report this event" (SRS 4.12): the report goes to Platform Admins, not the organizer. */
export function ReportEvent({ slug }: { slug: string }) {
  const t = useTranslations("report");
  const errorMessage = useErrorMessage();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  if (sent) return <Alert kind="success">{t("sent")}</Alert>;
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="text-sm text-gray-700 underline">
        {t("open")}
      </button>
    );
  }
  return (
    <form
      className="space-y-3 rounded-lg border border-gray-200 bg-white p-4"
      aria-labelledby="report-title"
      onSubmit={async (e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        setBusy(true);
        setError(null);
        try {
          await unwrap(
            api.POST("/api/v1/events/{slug}/report", {
              params: { path: { slug } },
              body: {
                reason: String(f.get("reason")) as Schemas["EventReportReason"],
                details: String(f.get("details") ?? "").trim() || null,
              },
            }),
          );
          setSent(true);
        } catch (err) {
          setError(err);
        } finally {
          setBusy(false);
        }
      }}
    >
      <h2 id="report-title" className="font-semibold text-gray-900">
        {t("title")}
      </h2>
      <p className="text-sm text-gray-700">{t("lead")}</p>
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      <Select name="reason" label={t("reason")} options={REASONS.map((r) => ({ value: r, label: t(`reasons.${r}`) }))} />
      <TextArea name="details" label={t("details")} rows={3} maxLength={2000} />
      <div className="flex gap-2">
        <Button type="submit" disabled={busy}>
          {t("submit")}
        </Button>
        <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}
