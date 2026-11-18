"use client";

import type { Schemas } from "@biletflow/api-types";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert, Field, Select } from "@/components/ui";
import { api, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

import { useOrganizerEvent } from "./event-shell";

/** SRS 4.16: the event's activity timeline from the append-only audit log, filterable by
 * date range and activity type. */
export function EventHistory() {
  const t = useTranslations("history");
  const tc = useTranslations("common");
  const format = useFormatter();
  const errorMessage = useErrorMessage();
  const { event } = useOrganizerEvent();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [category, setCategory] = useState("");
  const [result, setResult] = useState<{ key: string; data?: Schemas["Timeline"]; error?: unknown } | null>(null);
  const key = `${event.id}|${from}|${to}|${category}`;

  useEffect(() => {
    let active = true;
    unwrap(
      api.GET("/api/v1/history/events/{event_id}/timeline", {
        params: {
          path: { event_id: event.id },
          query: { date_from: from || null, date_to: to || null, category: category || null },
        },
      }),
    )
      .then((data) => active && setResult({ key, data }))
      .catch((error: unknown) => active && setResult({ key, error }));
    return () => {
      active = false;
    };
  }, [key, event.id, from, to, category]);

  const data = result?.data;
  const label = (c: string) => (t.has(`categories.${c}`) ? t(`categories.${c}`) : c);
  return (
    <div className="space-y-4">
      <p className="text-gray-600">{t("lead")}</p>
      <div className="flex flex-wrap items-end gap-3">
        <Select
          label={t("category")}
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          options={[{ value: "", label: t("allActivity") }, ...(data?.categories ?? []).map((c) => ({ value: c, label: label(c) }))]}
        />
        <Field type="date" label={t("from")} value={from} onChange={(e) => setFrom(e.target.value)} />
        <Field type="date" label={t("to")} value={to} onChange={(e) => setTo(e.target.value)} />
      </div>
      {result?.error ? <Alert kind="error">{errorMessage(result.error)}</Alert> : null}
      {!result && <p className="text-gray-600">{tc("loading")}</p>}
      {data && data.entries.length === 0 && <p className="text-gray-600">{t("empty")}</p>}
      {data && data.entries.length > 0 && (
        <ol className="relative space-y-4 border-l border-gray-200 pl-5">
          {data.entries.map((e) => (
            <li key={e.id} className="relative">
              <span aria-hidden="true" className="absolute -left-[25px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-gray-700" />
              <p className="text-sm text-gray-600">
                <time dateTime={e.occurred_at}>
                  {format.dateTime(new Date(e.occurred_at), { dateStyle: "medium", timeStyle: "short", timeZone: event.timezone })}
                </time>
                {" · "}
                {e.actor_name ?? t("system")}
                {" · "}
                <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-800">{label(e.category)}</span>
              </p>
              <p className="text-gray-900">{e.description}</p>
              <p className="font-mono text-xs text-gray-500">{e.action}</p>
            </li>
          ))}
        </ol>
      )}
      {data?.truncated && <p className="text-sm text-gray-600">{t("truncated")}</p>}
    </div>
  );
}
