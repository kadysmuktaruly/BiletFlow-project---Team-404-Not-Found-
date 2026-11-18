"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useParams, useSearchParams } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { Alert, Badge, Button, buttonClass, TAB_BAR, tabClass, TextArea } from "@/components/ui";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

export type OrganizerEvent = Schemas["EventRead"];

type EventContextValue = {
  event: OrganizerEvent;
  setEvent: (event: OrganizerEvent) => void;
};

const EventContext = createContext<EventContextValue | null>(null);

export function useOrganizerEvent(): EventContextValue {
  const ctx = useContext(EventContext);
  if (!ctx) throw new Error("useOrganizerEvent must be used inside <EventShell>");
  return ctx;
}

export function EventShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations();
  const errorMessage = useErrorMessage();
  const { eventId } = useParams<{ eventId: string }>();
  const pathname = usePathname();
  const router = useRouter();
  const justDuplicated = useSearchParams().get("duplicated") === "1";
  const [event, setEvent] = useState<OrganizerEvent | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    unwrap(
      api.GET("/api/v1/organizer/events/{event_id}", { params: { path: { event_id: eventId } } }),
    )
      .then(setEvent)
      .catch(setLoadError);
  }, [eventId]);

  const act = useCallback(
    async (action: "publish" | "unpublish" | "cancel", reason?: string) => {
      setBusy(true);
      setActionError(null);
      setNotice(null);
      const params = { params: { path: { event_id: eventId } } };
      try {
        const updated = await unwrap(
          action === "publish"
            ? api.POST("/api/v1/organizer/events/{event_id}/publish", params)
            : action === "unpublish"
              ? api.POST("/api/v1/organizer/events/{event_id}/unpublish", params)
              : api.POST("/api/v1/organizer/events/{event_id}/cancel", {
                  ...params,
                  body: { reason: reason || null },
                }),
        );
        setEvent(updated);
        setConfirmCancel(false);
        setNotice(
          action === "publish"
            ? t("organizer.manage.published")
            : action === "unpublish"
              ? t("organizer.manage.unpublished")
              : t("organizer.manage.cancelledNotice"),
        );
      } catch (err) {
        setActionError(err);
      } finally {
        setBusy(false);
      }
    },
    [eventId, t],
  );

  async function duplicate() {
    setBusy(true);
    setActionError(null);
    try {
      const copy = await unwrap(
        api.POST("/api/v1/organizer/events/{event_id}/duplicate", { params: { path: { event_id: eventId } } }),
      );
      router.push({ pathname: `/organizer/events/${copy.id}`, query: { duplicated: "1" } });
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  }

  if (loadError) return <Alert kind="error">{errorMessage(loadError)}</Alert>;
  if (!event) return <p className="text-ink-muted">{t("common.loading")}</p>;

  const base = `/organizer/events/${event.id}`;
  const tabs = [
    { href: base, label: t("organizer.manage.tabs.details") },
    { href: `${base}/tickets`, label: t("organizer.manage.tabs.tickets") },
    { href: `${base}/activation`, label: t("organizer.manage.tabs.activation") },
    { href: `${base}/campaigns`, label: t("organizer.manage.tabs.campaigns") },
    { href: `${base}/attendees`, label: t("organizer.manage.tabs.attendees") },
    { href: `${base}/orders`, label: t("organizer.manage.tabs.orders") },
    { href: `${base}/analytics`, label: t("organizer.manage.tabs.analytics") },
    { href: `${base}/history`, label: t("organizer.manage.tabs.history") },
    { href: `${base}/staff`, label: t("organizer.manage.tabs.staff") },
    { href: `${base}/preview`, label: t("organizer.manage.tabs.preview") },
  ];
  // SRS 4.16: past and cancelled events are read-only (the API enforces it).
  const closed = event.phase === "completed" || event.phase === "cancelled";

  return (
    <EventContext.Provider value={{ event, setEvent }}>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <Link href="/organizer/events" className="text-sm text-ink-muted underline decoration-1 underline-offset-4 hover:text-ink">
              {t("common.back")}
            </Link>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-display text-title text-ink">{event.title}</h1>
              <Badge tone={event.status === "published" ? "success" : event.status === "cancelled" ? "danger" : "neutral"}>
                {t(`event.status.${event.status}`)}
              </Badge>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href={{ pathname: "/support/new", query: { kind: "organizer", event: event.id } }}
              className={buttonClass("secondary")}
            >
              {t("support.contactPlatform")}
            </Link>
            <Button variant="secondary" disabled={busy} onClick={() => void duplicate()}>
              {t("organizer.manage.duplicate")}
            </Button>
            {event.status === "published" && (
              <Link
                href={`/events/${event.slug}`}
                className={buttonClass("secondary")}
              >
                {t("organizer.manage.viewPublic")}
              </Link>
            )}
            {!closed && (event.status === "draft" || event.status === "unpublished") && (
              <Button disabled={busy} onClick={() => void act("publish")}>
                {t("organizer.manage.publish")}
              </Button>
            )}
            {event.status === "published" && !closed && (
              <Button variant="secondary" disabled={busy} onClick={() => void act("unpublish")}>
                {t("organizer.manage.unpublish")}
              </Button>
            )}
            {!closed && (
              <Button variant="danger" disabled={busy} onClick={() => setConfirmCancel(true)}>
                {t("organizer.manage.cancel")}
              </Button>
            )}
          </div>
        </div>

        {closed && <Alert kind="info">{t("organizer.manage.readOnly")}</Alert>}
        {justDuplicated && <Alert kind="success">{t("organizer.manage.duplicated")}</Alert>}
        {notice && <Alert kind="success">{notice}</Alert>}
        {actionError ? <Alert kind="error">{errorMessage(actionError)}</Alert> : null}

        {confirmCancel && (
          <form
            className="space-y-3 rounded-card border border-danger/30 bg-danger-soft p-4"
            onSubmit={(e) => {
              e.preventDefault();
              void act("cancel", String(new FormData(e.currentTarget).get("reason") ?? ""));
            }}
          >
            <h2 className="font-semibold text-danger">{t("organizer.manage.cancelTitle")}</h2>
            <p className="text-sm text-danger">{t("organizer.manage.cancelText")}</p>
            <TextArea name="reason" label={t("organizer.manage.cancelReason")} rows={2} />
            <div className="flex gap-2">
              <Button type="submit" variant="danger" disabled={busy}>
                {t("organizer.manage.cancelDo")}
              </Button>
              <Button type="button" variant="secondary" onClick={() => setConfirmCancel(false)}>
                {t("organizer.manage.cancelKeep")}
              </Button>
            </div>
          </form>
        )}

        <nav aria-label={event.title} className="border-b border-line pb-3">
          <ul className={TAB_BAR}>
            {tabs.map((tab) => {
              const active = pathname === tab.href;
              return (
                <li key={tab.href}>
                  <Link
                    href={tab.href}
                    aria-current={active ? "page" : undefined}
                    className={tabClass(active)}
                  >
                    {tab.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        {children}
      </div>
    </EventContext.Provider>
  );
}
