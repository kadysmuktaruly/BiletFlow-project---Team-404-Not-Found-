"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { saveDownload } from "@/lib/download";
import { useErrorMessage } from "@/lib/use-error-message";

/** Download the print-optimized PDF of one ticket (SRS 4.7, UC7). */
export function TicketPdfButton({ ticketId, ticketNumber }: { ticketId: string; ticketNumber: string }) {
  const t = useTranslations("tickets");
  const errorMessage = useErrorMessage();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function download() {
    setBusy(true);
    setError(null);
    try {
      await saveDownload(
        api.GET("/api/v1/me/tickets/{ticket_id}/pdf", {
          params: { path: { ticket_id: ticketId } },
          parseAs: "blob",
        }),
        `ticket-${ticketNumber}.pdf`,
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-center gap-1">
      <Button
        variant="secondary"
        disabled={busy}
        onClick={() => void download()}
        aria-label={t("downloadPdfLabel", { number: ticketNumber })}
      >
        {t("downloadPdf")}
      </Button>
      {error ? (
        <p role="alert" className="text-sm text-red-700">
          {errorMessage(error)}
        </p>
      ) : null}
    </div>
  );
}
