"use client";

import type { Schemas } from "@biletflow/api-types";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert, PageTitle } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useErrorMessage } from "@/lib/use-error-message";

import { contextLine, STATUS_STYLE } from "./shared";

/** Support cases you opened and the ones you handle (SRS 4.13). */
export function SupportListPage() {
  const t = useTranslations("support");
  const tc = useTranslations("common");
  const format = useFormatter();
  const errorMessage = useErrorMessage();
  const { user } = useAuth();
  const [cases, setCases] = useState<Schemas["CaseSummary"][] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    const load = () =>
      unwrap(api.GET("/api/v1/support/cases"))
        .then((data) => active && setCases(data))
        .catch((err: unknown) => active && setError(err));
    void load();
    const timer = setInterval(load, 30_000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageTitle>{t("title")}</PageTitle>
        {user?.role === "organizer" && (
          <Link
            href={{ pathname: "/support/new", query: { kind: "organizer" } }}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-900 hover:bg-gray-50"
          >
            {t("contactPlatform")}
          </Link>
        )}
      </div>
      <p className="text-gray-600">{t("lead")}</p>
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      {!cases && !error && <p className="text-gray-600">{tc("loading")}</p>}
      {cases?.length === 0 && <p className="text-gray-600">{t("empty")}</p>}
      <ul className="space-y-3">
        {cases?.map((c) => (
          <li key={c.id} className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-semibold text-gray-900">
                <Link href={`/support/${c.id}`} className="underline-offset-4 hover:underline">
                  {c.subject}
                </Link>
              </h2>
              <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[c.status]}`}>
                {t(`status.${c.status}`)}
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-700">
              <span className="font-mono">{c.reference}</span> · {t(`category.${c.category}`)} · {contextLine(t, c.context)}
            </p>
            <p className="text-xs text-gray-600">
              {c.viewer_role === "requester" ? t("yours") : `${t("handling")} · ${c.requester.full_name}`}
              {c.last_message_at
                ? ` · ${format.dateTime(new Date(c.last_message_at), { dateStyle: "medium", timeStyle: "short" })}`
                : ""}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
