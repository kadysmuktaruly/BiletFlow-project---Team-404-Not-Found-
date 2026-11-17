"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";

const POLL_MS = 60_000;
const CHANGED = "biletflow:notifications-changed";

/** Tell the header badge to refresh now (after marking notifications read). */
export function notifyUnreadChanged(): void {
  window.dispatchEvent(new Event(CHANGED));
}

/** "Notifications" link with the unread count, refreshed by polling (no sockets needed). */
export function NotificationLink() {
  const t = useTranslations("nav");
  const [count, setCount] = useState(0);

  useEffect(() => {
    let active = true;
    const load = () =>
      unwrap(api.GET("/api/v1/me/notifications/unread-count"))
        .then((r) => active && setCount(r.unread_count))
        .catch(() => undefined);
    void load();
    const timer = setInterval(load, POLL_MS);
    window.addEventListener(CHANGED, load);
    return () => {
      active = false;
      clearInterval(timer);
      window.removeEventListener(CHANGED, load);
    };
  }, []);

  return (
    <Link href="/notifications" className="inline-flex items-center gap-1.5 text-gray-700 hover:text-gray-900">
      {t("notifications")}
      {count > 0 && (
        <span className="rounded-full bg-red-700 px-1.5 py-0.5 text-xs font-bold leading-none text-white">
          <span aria-hidden="true">{count}</span>
          <span className="sr-only">{t("unread", { count })}</span>
        </span>
      )}
    </Link>
  );
}
