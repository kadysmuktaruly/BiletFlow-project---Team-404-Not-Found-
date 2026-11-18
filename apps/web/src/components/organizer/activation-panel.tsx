"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert, Button, Card, DemoBadge } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { newIdempotencyKey, useMoney } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

import { useOrganizerEvent } from "./event-shell";

type Activation = Schemas["ActivationRead"];

export function ActivationPanel() {
  const t = useTranslations("organizer.activation");
  const tc = useTranslations("common");
  const money = useMoney();
  const errorMessage = useErrorMessage();
  const { event } = useOrganizerEvent();
  const [state, setState] = useState<Activation | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [feeFailed, setFeeFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const path = { params: { path: { event_id: event.id } } };

  useEffect(() => {
    unwrap(
      api.GET("/api/v1/organizer/events/{event_id}/activation", {
        params: { path: { event_id: event.id } },
      }),
    )
      .then(setState)
      .catch(setError);
  }, [event.id]);

  async function run(call: () => Promise<Activation>) {
    setBusy(true);
    setError(null);
    try {
      setState(await call());
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function payFee(outcome: "succeed" | "fail") {
    setFeeFailed(false);
    await run(async () => {
      const result = await unwrap(
        api.POST("/api/v1/organizer/events/{event_id}/activation/fee-payment", {
          ...path,
          params: { ...path.params, header: { "Idempotency-Key": newIdempotencyKey() } },
          body: { outcome },
        }),
      );
      if (!result.activation_fee_paid) setFeeFailed(true);
      return result;
    });
  }

  if (!state) {
    return error ? <Alert kind="error">{errorMessage(error)}</Alert> : <p className="text-ink-muted">{tc("loading")}</p>;
  }

  const confirm = { confirm: true as const };
  const steps = [
    {
      key: "paidTicket",
      done: state.has_paid_ticket_type,
      action: (
        <Link href={`/organizer/events/${event.id}/tickets`} className="text-sm font-semibold text-sky-ink underline decoration-1 underline-offset-4 hover:decoration-2">
          {t("goToTickets")}
        </Link>
      ),
    },
    {
      key: "identity",
      done: state.identity_verified,
      action: (
        <Button
          variant="secondary"
          disabled={busy}
          onClick={() =>
            void run(() => unwrap(api.POST("/api/v1/organizer/events/{event_id}/activation/identity", { ...path, body: confirm })))
          }
        >
          {t("verify")}
        </Button>
      ),
    },
    {
      key: "payout",
      done: state.payout_account_connected,
      action: (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() =>
              void run(() =>
                unwrap(api.POST("/api/v1/organizer/events/{event_id}/activation/payout-account", { ...path, body: confirm })),
              )
            }
          >
            {t("connect")}
          </Button>
          <Link href="/organizer/profile" className="text-sm text-ink-muted underline decoration-1 underline-offset-4 hover:text-ink">
            {t("goToProfile")}
          </Link>
        </div>
      ),
    },
    {
      key: "fee",
      done: state.activation_fee_paid,
      action: (
        <div className="flex flex-wrap gap-2">
          <Button disabled={busy} onClick={() => void payFee("succeed")}>
            {t("paySucceed")}
          </Button>
          <Button variant="secondary" disabled={busy} onClick={() => void payFee("fail")}>
            {t("payFail")}
          </Button>
        </div>
      ),
    },
    {
      key: "terms",
      done: state.terms_accepted,
      action: (
        <Button
          variant="secondary"
          disabled={busy}
          onClick={() =>
            void run(() => unwrap(api.POST("/api/v1/organizer/events/{event_id}/activation/terms", { ...path, body: confirm })))
          }
        >
          {t("accept")}
        </Button>
      ),
    },
  ] as const;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-ink-muted">{t("lead")}</p>
        <DemoBadge label={tc("demo")} />
      </div>
      <Alert kind="demo">{t("demoNotice")}</Alert>
      <p className="font-medium text-ink">{t("statusLabel", { status: t(`status.${state.status}`) })}</p>
      {state.paid_sales_enabled && <Alert kind="success">{t("enabled")}</Alert>}
      {state.status === "suspended" && <Alert kind="error">{t("suspended")}</Alert>}
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      {feeFailed && <Alert kind="error">{t("feeFailed")}</Alert>}
      <ol className="space-y-3">
        {steps.map((step, i) => (
          <li key={step.key}>
            <Card className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-ink">
                  {i + 1}. {t(`steps.${step.key}.title`)}
                </p>
                <p className="text-sm text-ink-muted">
                  {t(`steps.${step.key}.text`, { amount: money(state.activation_fee_kzt) })}
                </p>
              </div>
              {step.done ? (
                <span className="rounded-full bg-success-soft px-3 py-1 text-sm font-semibold text-success">
                  ✓ {t("done")}
                </span>
              ) : (
                step.action
              )}
            </Card>
          </li>
        ))}
      </ol>
    </div>
  );
}
