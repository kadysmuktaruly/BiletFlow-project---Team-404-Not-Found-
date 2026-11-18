"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { Alert, Button, TextArea } from "@/components/ui";
import { Link, usePathname } from "@/i18n/navigation";
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

  if (loadError) return <Alert kind="error">{errorMessage(loadError)}</Alert>;
  if (!event) return <p className="text-gray-600">{t("common.loading")}</p>;

  const base = `/organizer/events/${event.id}`;
  const tabs = [
    { href: base, label: t("organizer.manage.tabs.details") },
    { href: `${base}/tickets`, label: t("organizer.manage.tabs.tickets") },
    { href: `${base}/activation`, label: t("organizer.manage.tabs.activation") },
    { href: `${base}/staff`, label: t("organizer.manage.tabs.staff") },
    { href: `${base}/preview`, label: t("organizer.manage.tabs.preview") },
  ];
  const closed = event.status === "cancelled" || event.status === "completed";

  return (
    <EventContext.Provider value={{ event, setEvent }}>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <Link href="/organizer/events" className="text-sm text-gray-600 underline">
              {t("common.back")}
            </Link>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-gray-900">{event.title}</h1>
              <span className="rounded-full border border-gray-300 px-2 py-0.5 text-xs font-medium text-gray-800">
                {t(`event.status.${event.status}`)}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {event.status === "published" && (
              <Link
                href={`/events/${event.slug}`}
                className="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-900 hover:bg-gray-50"
              >
                {t("organizer.manage.viewPublic")}
              </Link>
            )}
            {(event.status === "draft" || event.status === "unpublished") && (
              <Button disabled={busy} onClick={() => void act("publish")}>
                {t("organizer.manage.publish")}
              </Button>
            )}
            {event.status === "published" && (
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

        {notice && <Alert kind="success">{notice}</Alert>}
        {actionError ? <Alert kind="error">{errorMessage(actionError)}</Alert> : null}

        {confirmCancel && (
          <form
            className="space-y-3 rounded-lg border border-red-300 bg-red-50 p-4"
            onSubmit={(e) => {
              e.preventDefault();
              void act("cancel", String(new FormData(e.currentTarget).get("reason") ?? ""));
            }}
          >
            <h2 className="font-semibold text-red-900">{t("organizer.manage.cancelTitle")}</h2>
            <p className="text-sm text-red-900">{t("organizer.manage.cancelText")}</p>
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

        <nav aria-label={event.title} className="border-b border-gray-200">
          <ul className="-mb-px flex flex-wrap gap-4 text-sm">
            {tabs.map((tab) => {
              const active = pathname === tab.href;
              return (
                <li key={tab.href}>
                  <Link
                    href={tab.href}
                    aria-current={active ? "page" : undefined}
                    className={`inline-block border-b-2 px-1 py-2 font-medium ${active ? "border-gray-900 text-gray-900" : "border-transparent text-gray-600 hover:text-gray-900"}`}
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
