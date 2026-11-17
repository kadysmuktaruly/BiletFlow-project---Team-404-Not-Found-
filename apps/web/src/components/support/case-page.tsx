"use client";

import type { Schemas } from "@biletflow/api-types";
import { useFormatter, useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Alert, Button, Card, PageTitle, Select, TextArea } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

import { contextLine, STATUSES, STATUS_STYLE } from "./shared";

type Case = Schemas["CaseRead"];
const POLL_MS = 10_000;

/** One support case: the asynchronous thread (polled, SRS 4.13), a reply box, and for the
 * people handling it, status, assignment and internal notes. */
export function CasePage() {
  const t = useTranslations("support");
  const tc = useTranslations("common");
  const format = useFormatter();
  const errorMessage = useErrorMessage();
  const { caseId } = useParams<{ caseId: string }>();
  const [item, setItem] = useState<Case | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const fetchCase = useCallback(
    () => unwrap(api.GET("/api/v1/support/cases/{case_id}", { params: { path: { case_id: caseId } } })),
    [caseId],
  );

  useEffect(() => {
    let active = true;
    const load = () =>
      fetchCase()
        .then((c) => active && setItem(c))
        .catch((err: unknown) => active && setError(err));
    void load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [fetchCase]);

  async function reply(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const body = String(f.get("body") ?? "").trim();
    if (!body) return;
    setBusy(true);
    setActionError(null);
    try {
      setItem(
        await unwrap(
          api.POST("/api/v1/support/cases/{case_id}/messages", {
            params: { path: { case_id: caseId } },
            body: { body, internal: f.get("internal") === "on" },
          }),
        ),
      );
      form.reset();
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  }

  async function manage(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const assignee = String(f.get("assignee") ?? "");
    setBusy(true);
    setActionError(null);
    try {
      setItem(
        await unwrap(
          api.PATCH("/api/v1/support/cases/{case_id}", {
            params: { path: { case_id: caseId } },
            body: {
              status: String(f.get("status")) as Case["status"],
              assigned_to_user_id: assignee || null,
            },
          }),
        ),
      );
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  }

  if (error && !item) return <Alert kind="error">{errorMessage(error)}</Alert>;
  if (!item) return <p className="text-gray-600">{tc("loading")}</p>;

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <Link href="/support" className="text-sm text-gray-600 underline">
          {tc("back")}
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <PageTitle>{item.subject}</PageTitle>
          <span className={`-mt-6 rounded-full border px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[item.status]}`}>
            <span className="sr-only">{t("status.label")}: </span>
            {t(`status.${item.status}`)}
          </span>
        </div>
        <p className="text-sm text-gray-700">
          <span className="font-mono">{item.reference}</span> · {t(`kind.${item.kind}`)} · {t(`category.${item.category}`)} ·{" "}
          {contextLine(t, item.context)}
        </p>
        <p className="text-sm text-gray-700">
          {t("thread.requester")}: {item.requester.full_name} · {t("thread.assignedTo")}:{" "}
          {item.assigned_to?.full_name ?? t("thread.nobody")}
        </p>
      </div>

      <ol className="space-y-3" aria-live="polite">
        {item.messages.map((m) => (
          <li
            key={m.id}
            className={`rounded-lg border p-4 ${
              m.internal
                ? "border-dashed border-amber-400 bg-amber-50"
                : m.from_staff
                  ? "border-gray-300 bg-white"
                  : "border-gray-200 bg-gray-50"
            }`}
          >
            <p className="text-sm font-semibold text-gray-900">
              {m.author.full_name}
              {m.from_staff && <span className="ml-2 font-normal text-gray-600">({t("thread.staff")})</span>}
              {m.internal && (
                <span className="ml-2 rounded bg-amber-200 px-1.5 py-0.5 text-xs font-bold text-amber-950">{t("thread.internal")}</span>
              )}
            </p>
            <p className="mt-1 whitespace-pre-line text-gray-800">{m.body}</p>
            <time dateTime={m.created_at} className="mt-1 block text-xs text-gray-600">
              {format.dateTime(new Date(m.created_at), { dateStyle: "medium", timeStyle: "short" })}
            </time>
          </li>
        ))}
      </ol>
      <p className="text-xs text-gray-600">{t("thread.refreshNote")}</p>

      {actionError ? <Alert kind="error">{errorMessage(actionError)}</Alert> : null}
      <Card>
        <form onSubmit={reply} className="space-y-3">
          <TextArea name="body" label={t("thread.reply")} required maxLength={5000} rows={4} />
          {item.can_manage && (
            <label className="flex items-center gap-2 text-sm text-gray-900">
              <input type="checkbox" name="internal" className="h-4 w-4" />
              {t("thread.internalNote")}
            </label>
          )}
          <Button type="submit" disabled={busy}>
            {t("thread.send")}
          </Button>
        </form>
      </Card>

      {item.can_manage && (
        <Card>
          <h2 className="mb-3 text-lg font-semibold text-gray-900">{t("thread.manage")}</h2>
          <form onSubmit={manage} className="grid gap-4 sm:grid-cols-2">
            <Select
              name="status"
              label={t("status.label")}
              defaultValue={item.status}
              options={STATUSES.map((s) => ({ value: s, label: t(`status.${s}`) }))}
            />
            <Select
              name="assignee"
              label={t("thread.assign")}
              defaultValue={item.assigned_to?.id ?? ""}
              options={[
                { value: "", label: t("thread.nobody") },
                ...item.assignees.map((p) => ({ value: p.id, label: p.full_name })),
              ]}
            />
            <div className="sm:col-span-2">
              <Button type="submit" variant="secondary" disabled={busy}>
                {t("thread.save")}
              </Button>
            </div>
          </form>
        </Card>
      )}
    </div>
  );
}
