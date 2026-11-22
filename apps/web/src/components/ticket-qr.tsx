"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";

import { Button, buttonClass } from "./ui";

/**
 * The ticket's admission QR, rendered by the API as SVG (the same image as in the email).
 * With `enlargeable`, a button opens it full screen (a modal `<dialog>`: focus is trapped,
 * Escape closes it) so it scans easily at the door or off a projected screen.
 */
export function TicketQr({
  ticketId,
  ticketNumber,
  enlargeable = false,
}: {
  ticketId: string;
  ticketNumber: string;
  enlargeable?: boolean;
}) {
  const t = useTranslations("tickets");
  const [src, setSrc] = useState<string | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);

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

  const alt = t("qrAlt", { number: ticketNumber });

  return (
    <>
      <div className="flex h-48 w-48 items-center justify-center rounded-field bg-surface p-2 ring-1 ring-line">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element -- inline SVG data URL
          <img src={src} alt={alt} className="h-full w-full" />
        ) : null}
      </div>
      {enlargeable && src && (
        <>
          <button
            type="button"
            className={buttonClass("secondary", "sm")}
            aria-label={t("fullScreenLabel", { number: ticketNumber })}
            onClick={() => dialog.current?.showModal()}
          >
            {t("fullScreen")}
          </button>
          <dialog
            ref={dialog}
            aria-label={alt}
            className="m-auto max-h-none max-w-none bg-transparent p-0 backdrop:bg-ink/90"
            onClick={(e) => {
              // A click on the backdrop (the dialog element itself) closes it.
              if (e.target === e.currentTarget) e.currentTarget.close();
            }}
          >
            <div className="flex flex-col items-center gap-4 rounded-card bg-surface p-4 sm:p-6">
              {/* White, square and as large as the viewport allows, keeping the quiet zone. */}
              {/* eslint-disable-next-line @next/next/no-img-element -- inline SVG data URL */}
              <img src={src} alt={alt} className="h-[min(80vw,75vh)] w-[min(80vw,75vh)] bg-surface" />
              <p className="font-mono text-2xl font-bold tracking-wider text-ink">{ticketNumber}</p>
              <Button type="button" variant="secondary" autoFocus onClick={() => dialog.current?.close()}>
                {t("closeFullScreen")}
              </Button>
            </div>
          </dialog>
        </>
      )}
    </>
  );
}
