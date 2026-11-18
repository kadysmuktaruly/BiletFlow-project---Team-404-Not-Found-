"use client";

import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Resolve a Campaign QR token, then open its event with the promo code pre-applied. The
 * code arrives only if the server says the campaign can be used right now. */
export function CampaignLanding() {
  const t = useTranslations("campaignLink");
  const router = useRouter();
  const { token } = useParams<{ token: string }>();
  const { status } = useAuth();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    // Wait for the session, so a private event's campaign works for its staff.
    if (status === "loading") return;
    unwrap(api.GET("/api/v1/campaigns/resolve/{token}", { params: { path: { token: decodeURIComponent(token) } } }))
      .then((r) => {
        const query: Record<string, string> = r.code ? { promo: r.code } : r.rejection ? { promo_rejected: r.rejection } : {};
        router.replace({ pathname: `/events/${r.event_slug}`, query });
      })
      .catch(() => setFailed(true));
  }, [token, status, router]);

  if (failed) {
    return (
      <div className="space-y-4">
        <Alert kind="error">{t("invalid")}</Alert>
        <Link href="/events" className="font-semibold text-sky-ink underline decoration-1 underline-offset-4 hover:decoration-2">
          {t("browse")}
        </Link>
      </div>
    );
  }
  return (
    <p className="text-ink-muted" aria-live="polite">
      {t("opening")}
    </p>
  );
}
