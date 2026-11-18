"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Alert, Button, Card, Field } from "@/components/ui";
import { api, ApiError, unwrap } from "@/lib/api";
import { useMoney } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

import { useOrganizerEvent } from "./event-shell";

type TicketType = Schemas["TicketTypeRead"];

const blankToNull = (v: FormDataEntryValue | null) => (v && String(v).trim() ? String(v) : null);

export function TicketTypesPanel() {
  const t = useTranslations("organizer.ticketTypes");
  const tc = useTranslations("common");
  const money = useMoney();
  const errorMessage = useErrorMessage();
  const { event } = useOrganizerEvent();
  const [types, setTypes] = useState<TicketType[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [formError, setFormError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const path = { params: { path: { event_id: event.id } } };

  const load = useCallback(async () => {
    try {
      setTypes(await unwrap(api.GET("/api/v1/organizer/events/{event_id}/ticket-types", path)));
    } catch (err) {
      setError(err);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `path` is derived from event.id
  }, [event.id]);

  useEffect(() => {
    let active = true;
    unwrap(
      api.GET("/api/v1/organizer/events/{event_id}/ticket-types", {
        params: { path: { event_id: event.id } },
      }),
    )
      .then((data) => active && setTypes(data))
      .catch((err: unknown) => active && setError(err));
    return () => {
      active = false;
    };
  }, [event.id]);

  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    setBusy(true);
    setFormError(null);
    try {
      await unwrap(
        api.POST("/api/v1/organizer/events/{event_id}/ticket-types", {
          ...path,
          body: {
            name: String(f.get("name")),
            description: blankToNull(f.get("description")),
            price_kzt: Number(f.get("price_kzt") || 0),
            quantity_total: Number(f.get("quantity_total") || 0),
            max_per_order: Number(f.get("max_per_order") || 10),
            sales_start_at: blankToNull(f.get("sales_start_at")),
            sales_end_at: blankToNull(f.get("sales_end_at")),
            is_hidden: false,
          },
        }),
      );
      form.reset();
      await load();
    } catch (err) {
      setFormError(err);
    } finally {
      setBusy(false);
    }
  }

  async function patch(id: string, body: Schemas["TicketTypeUpdate"]) {
    setError(null);
    try {
      await unwrap(
        api.PATCH("/api/v1/organizer/events/{event_id}/ticket-types/{ticket_type_id}", {
          params: { path: { event_id: event.id, ticket_type_id: id } },
          body,
        }),
      );
      await load();
    } catch (err) {
      setError(err);
    }
  }

  async function remove(id: string) {
    if (!window.confirm(t("deleteConfirm"))) return;
    setError(null);
    try {
      await unwrap(
        api.DELETE("/api/v1/organizer/events/{event_id}/ticket-types/{ticket_type_id}", {
          params: { path: { event_id: event.id, ticket_type_id: id } },
        }),
      );
      await load();
    } catch (err) {
      setError(err);
    }
  }

  const fields = formError instanceof ApiError ? formError.fields : {};
  return (
    <div className="space-y-6">
      <p className="text-gray-600">{t("lead")}</p>
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      {types === null && !error && <p className="text-gray-600">{tc("loading")}</p>}
      {types?.length === 0 && <p className="text-gray-600">{t("empty")}</p>}
      {types && types.length > 0 && (
        <ul className="space-y-3">
          {types.map((tt) => (
            <li key={tt.id} className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="font-semibold text-gray-900">
                  {tt.name}
                  {tt.is_hidden && (
                    <span className="ml-2 rounded bg-gray-200 px-1.5 py-0.5 text-xs font-medium text-gray-800">
                      {t("hidden")}
                    </span>
                  )}
                </p>
                <p className="font-semibold text-gray-900">{tt.is_free ? t("free") : money(tt.price_kzt)}</p>
              </div>
              <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-5">
                {(
                  [
                    ["available", tt.quantity_available],
                    ["reserved", tt.quantity_reserved],
                    ["sold", tt.quantity_sold],
                    ["refunded", tt.quantity_refunded],
                    ["checkedIn", tt.quantity_checked_in],
                  ] as const
                ).map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-gray-600">{t(`counts.${key}`)}</dt>
                    <dd className="font-medium text-gray-900">
                      {value}
                      {key === "available" ? ` / ${tt.quantity_total}` : ""}
                    </dd>
                  </div>
                ))}
              </dl>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button variant="secondary" onClick={() => void patch(tt.id, { is_hidden: !tt.is_hidden })}>
                  {tt.is_hidden ? t("show") : t("hide")}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => {
                    const value = window.prompt(t("quantity"), String(tt.quantity_total));
                    if (value !== null && value.trim()) void patch(tt.id, { quantity_total: Number(value) });
                  }}
                >
                  {t("quantity")}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => {
                    const value = window.prompt(t("price"), String(tt.price_kzt));
                    if (value !== null && value.trim()) void patch(tt.id, { price_kzt: Number(value) });
                  }}
                >
                  {t("price")}
                </Button>
                <Button variant="danger" onClick={() => void remove(tt.id)}>
                  {tc("delete")}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Card>
        <h2 className="mb-4 text-lg font-semibold text-gray-900">{t("add")}</h2>
        <form onSubmit={create} className="grid gap-4 sm:grid-cols-2" noValidate>
          {formError ? (
            <div className="sm:col-span-2">
              <Alert kind="error">{errorMessage(formError)}</Alert>
            </div>
          ) : null}
          <Field name="name" label={t("name")} required maxLength={200} error={fields.name && errorMessage(formError)} />
          <Field name="description" label={`${t("description")} (${tc("optional")})`} />
          <Field name="price_kzt" type="number" min={0} step={1} label={t("price")} hint={t("priceHint")} defaultValue={0} required />
          <Field name="quantity_total" type="number" min={0} step={1} label={t("quantity")} defaultValue={100} required />
          <Field name="max_per_order" type="number" min={1} max={100} label={t("maxPerOrder")} defaultValue={10} />
          <div />
          <Field name="sales_start_at" type="datetime-local" label={`${t("salesStart")} (${tc("optional")})`} />
          <Field name="sales_end_at" type="datetime-local" label={`${t("salesEnd")} (${tc("optional")})`} />
          <div className="sm:col-span-2">
            <Button type="submit" disabled={busy}>
              {t("add")}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
