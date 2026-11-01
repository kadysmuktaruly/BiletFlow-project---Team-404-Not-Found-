"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";

/** The ticket's admission QR, rendered by the API as SVG (the same image as in the email). */
export function TicketQr({ ticketId, ticketNumber }: { ticketId: string; ticketNumber: string }) {
  const t = useTranslations("tickets");
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api
      .GET("/api/v1/me/tickets/{ticket_id}/qr.svg", {
        params: { path: { ticket_id: ticketId } },
        parseAs: "text",
      })
      .then(({ data }) => {
        if (active && typeof data === "string") {
          setSrc(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(data)}`);
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [ticketId]);

  return (
    <div className="flex h-48 w-48 items-center justify-center rounded-md border border-gray-200 bg-white">
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element -- inline SVG data URL
        <img src={src} alt={t("qrAlt", { number: ticketNumber })} className="h-full w-full" />
      ) : null}
    </div>
  );
}
