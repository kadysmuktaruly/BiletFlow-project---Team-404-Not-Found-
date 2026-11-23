"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { Alert, Button, buttonClass, Card, PageTitle, SECTION_TITLE } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api, ApiError, unwrap } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useErrorMessage } from "@/lib/use-error-message";

type SelfServiceRole = "attendee" | "organizer";

/** The signed-in user's account: switch between attendee and organizer (PUT /me/role). */
export function AccountPage() {
  const t = useTranslations("account");
  const tc = useTranslations("common");
  const errorMessage = useErrorMessage();
  const { user, setUser } = useAuth();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [switched, setSwitched] = useState(false);

  if (!user) return null;
  const role = user.role;
  const selfService = role === "attendee" || role === "organizer";
  const target: SelfServiceRole = role === "organizer" ? "attendee" : "organizer";
  const roleLabel = (r: string) => (r === "organizer" ? t("roleOrganizer") : t("roleAttendee"));

  async function switchRole() {
    setBusy(true);
    setError(null);
    setSwitched(false);
    try {
      setUser(await unwrap(api.PUT("/api/v1/me/role", { body: { role: target } })));
      setSwitched(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  const liveEvents = error instanceof ApiError && error.code === "organizer_has_active_events";

  return (
    <div className="mx-auto max-w-xl">
      <PageTitle>{t("title")}</PageTitle>
      <Card className="space-y-4">
        <p className="text-sm text-ink-muted">{t("current", { email: user.email })}</p>
        <h2 className={SECTION_TITLE}>
          {selfService ? `${t("roleHeading")}: ${roleLabel(role)}` : t("roleHeading")}
        </h2>
        {!selfService ? (
          <p className="text-sm text-ink">{t("fixedRole")}</p>
        ) : (
          <>
            <p className="text-sm text-ink">
              {role === "organizer" ? t("organizerText") : t("attendeeText")}
            </p>
            {switched && <Alert kind="success">{t("switched", { role: roleLabel(role) })}</Alert>}
            {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
            {liveEvents && (
              <Link href="/organizer/events" className={`${buttonClass("secondary")} w-full`}>
                {t("seeEvents")}
              </Link>
            )}
            {confirming ? (
              <ConfirmDialog
                title={target === "organizer" ? t("confirmOrganizerTitle") : t("confirmAttendeeTitle")}
                text={target === "organizer" ? t("confirmOrganizerText") : t("confirmAttendeeText")}
                confirmLabel={target === "organizer" ? t("becomeOrganizer") : t("switchToAttendee")}
                cancelLabel={tc("cancel")}
                busy={busy}
                danger={false}
                onConfirm={switchRole}
                onCancel={() => setConfirming(false)}
              />
            ) : (
              <Button
                type="button"
                variant={target === "organizer" ? "primary" : "secondary"}
                className="w-full"
                onClick={() => setConfirming(true)}
              >
                {target === "organizer" ? t("becomeOrganizer") : t("switchToAttendee")}
              </Button>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
