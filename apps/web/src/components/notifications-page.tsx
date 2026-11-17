"use client";

import type { Schemas } from "@biletflow/api-types";
import { useFormatter, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Alert, Button, PageTitle } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

import { notifyUnreadChanged } from "./notification-badge";

type Inbox = Schemas["NotificationList"];

/** The in-app notification center (SRS 4.10). Every item was also sent by email. */
export function NotificationsPage() {
  const t = useTranslations("notifications");
  const tc = useTranslations("common");
  const format = useFormatter();
  const errorMessage = useErrorMessage();
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [error, setError] = useState<unknown>(null);

  const fetchInbox = useCallback(() => unwrap(api.GET("/api/v1/me/notifications", { params: { query: { limit: 100 } } })), []);

  useEffect(() => {
    let active = true;
    fetchInbox()
      .then((data) => active && setInbox(data))
      .catch((err: unknown) => active && setError(err));
    return () => {
      active = false;
    };
  }, [fetchInbox]);

  async function markRead(id: string) {
    try {
      await unwrap(api.POST("/api/v1/me/notifications/{notification_id}/read", { params: { path: { notification_id: id } } }));
      setInbox(await fetchInbox());
      notifyUnreadChanged();
    } catch (err) {
      setError(err);
    }
  }

  async function markAll() {
    try {
      await unwrap(api.POST("/api/v1/me/notifications/read-all"));
      setInbox(await fetchInbox());
      notifyUnreadChanged();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageTitle>{t("title")}</PageTitle>
        {inbox && inbox.unread_count > 0 && (
          <Button variant="secondary" onClick={() => void markAll()}>
            {t("markAll")}
          </Button>
        )}
      </div>
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      {!inbox && !error && <p className="text-gray-600">{tc("loading")}</p>}
      {inbox && (
        <p className="text-sm text-gray-700" aria-live="polite">
          {t("unreadCount", { count: inbox.unread_count })}
        </p>
      )}
      {inbox?.items.length === 0 && <p className="text-gray-600">{t("empty")}</p>}
      {inbox && inbox.items.length > 0 && (
        <ul className="space-y-3">
          {inbox.items.map((n) => {
            const unread = n.read_at === null;
            return (
              <li
                key={n.id}
                className={`rounded-lg border p-4 ${unread ? "border-gray-900 bg-white" : "border-gray-200 bg-gray-50"}`}
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h2 className="font-semibold text-gray-900">
                    {unread && <span className="mr-2 rounded bg-gray-900 px-1.5 py-0.5 text-xs font-bold text-white">{t("new")}</span>}
                    {n.subject}
                  </h2>
                  <time dateTime={n.created_at} className="text-sm text-gray-600">
                    {format.dateTime(new Date(n.created_at), { dateStyle: "medium", timeStyle: "short" })}
                  </time>
                </div>
                <p className="mt-1 text-gray-800">{n.body}</p>
                <div className="mt-2 flex flex-wrap gap-4 text-sm">
                  {n.action_path && (
                    <Link
                      href={n.action_path}
                      onClick={() => unread && void markRead(n.id)}
                      className="font-medium text-gray-900 underline"
                    >
                      {t("open")}
                    </Link>
                  )}
                  {unread && (
                    <button type="button" onClick={() => void markRead(n.id)} className="text-gray-700 underline">
                      {t("markRead")}
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
