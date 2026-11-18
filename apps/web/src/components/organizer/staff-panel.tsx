"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Alert, Button, Card, Field, Select } from "@/components/ui";
import { api, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

import { useOrganizerEvent } from "./event-shell";

type Staff = Schemas["StaffRead"];

export function StaffPanel() {
  const t = useTranslations("organizer.staff");
  const tc = useTranslations("common");
  const errorMessage = useErrorMessage();
  const { event } = useOrganizerEvent();
  const [staff, setStaff] = useState<Staff[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [added, setAdded] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setStaff(
      await unwrap(
        api.GET("/api/v1/organizer/events/{event_id}/staff", { params: { path: { event_id: event.id } } }),
      ),
    );
  }, [event.id]);

  useEffect(() => {
    unwrap(api.GET("/api/v1/organizer/events/{event_id}/staff", { params: { path: { event_id: event.id } } }))
      .then(setStaff)
      .catch(setError);
  }, [event.id]);

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    setBusy(true);
    setError(null);
    setAdded(false);
    try {
      await unwrap(
        api.POST("/api/v1/organizer/events/{event_id}/staff", {
          params: { path: { event_id: event.id } },
          body: {
            email: String(f.get("email")),
            role: String(f.get("role")) as "event_admin" | "check_in_staff",
          },
        }),
      );
      form.reset();
      setAdded(true);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setError(null);
    try {
      await unwrap(
        api.DELETE("/api/v1/organizer/events/{event_id}/staff/{assignment_id}", {
          params: { path: { event_id: event.id, assignment_id: id } },
        }),
      );
      await load();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <div className="space-y-6">
      <p className="text-gray-700">{t("lead")}</p>
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      {staff === null && !error && <p className="text-gray-600">{tc("loading")}</p>}
      {staff?.length === 0 && <p className="text-gray-600">{t("empty")}</p>}
      {staff && staff.length > 0 && (
        <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
          {staff.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center gap-4 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-gray-900">{s.full_name}</p>
                <p className="text-sm text-gray-600">
                  {s.email} · {t(`roles.${s.role}`)}
                </p>
              </div>
              <Button variant="secondary" onClick={() => void remove(s.id)}>
                {tc("remove")}
              </Button>
            </li>
          ))}
        </ul>
      )}
      <Card>
        <form onSubmit={add} className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <Field name="email" type="email" label={t("email")} required />
          <Select
            name="role"
            label={t("role")}
            defaultValue="event_admin"
            options={(["event_admin", "check_in_staff"] as const).map((r) => ({ value: r, label: t(`roles.${r}`) }))}
          />
          <Button type="submit" disabled={busy}>
            {t("add")}
          </Button>
        </form>
        {added && <p className="mt-3 text-sm text-green-800">{t("added")}</p>}
      </Card>
    </div>
  );
}
