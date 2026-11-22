"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { saveDownload } from "@/lib/download";
import { useErrorMessage } from "@/lib/use-error-message";

type Lang = "kk" | "ru" | "en";

/**
 * Download the event as an .ics file. The API writes it in the event's own time zone, so the
 * calendar shows the local start time. It goes through the typed client so private events
 * (open only to their staff) work too.
 */
export function AddToCalendar({ slug, title }: { slug: string; title: string }) {
  const t = useTranslations("calendar");
  const locale = useLocale() as Lang;
  const errorMessage = useErrorMessage();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function download() {
    setBusy(true);
    setError(null);
    try {
      await saveDownload(
        api.GET("/api/v1/events/{slug}/calendar.ics", {
          params: { path: { slug }, query: { lang: locale } },
          parseAs: "blob",
        }),
        `${slug}.ics`,
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <Button
        variant="secondary"
        size="sm"
        disabled={busy}
        onClick={() => void download()}
        aria-label={t("addLabel", { title })}
      >
        {t("add")}
      </Button>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {errorMessage(error)}
        </p>
      ) : null}
    </div>
  );
}
