"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { EventView, type PublicEvent } from "@/components/event-view";
import { Alert } from "@/components/ui";
import { api, unwrap } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useErrorMessage } from "@/lib/use-error-message";

import { PurchasePanel } from "./purchase-panel";

export function EventPage() {
  const t = useTranslations("common");
  const errorMessage = useErrorMessage();
  const { slug } = useParams<{ slug: string }>();
  // Set by the Campaign QR landing page (/c/[token]) after the server resolved the campaign.
  const search = useSearchParams();
  const promo = search.get("promo");
  const promoRejected = search.get("promo_rejected");
  const { status } = useAuth();
  const [event, setEvent] = useState<PublicEvent | null>(null);
  const [error, setError] = useState<unknown>(null);

  // Wait for the session to be restored: private events open only for their staff.
  useEffect(() => {
    if (status === "loading") return;
    unwrap(api.GET("/api/v1/events/{slug}", { params: { path: { slug } } }))
      .then(setEvent)
      .catch(setError);
  }, [slug, status]);

  if (error) return <Alert kind="error">{errorMessage(error)}</Alert>;
  if (!event) return <p className="text-gray-600">{t("loading")}</p>;
  return (
    <EventView
      event={event}
      ticketSlot={<PurchasePanel event={event} initialPromo={promo} campaignRejection={promoRejected} />}
    />
  );
}
