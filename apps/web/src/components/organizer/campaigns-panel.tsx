"use client";

import type { Schemas } from "@biletflow/api-types";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Alert, Button, Card, DemoBadge, Field, Select } from "@/components/ui";
import { api, ApiError, unwrap } from "@/lib/api";
import { saveDownload } from "@/lib/download";
import { useMoney } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

import { useOrganizerEvent } from "./event-shell";

type Campaign = Schemas["CampaignRead"];
type TicketType = Schemas["TicketTypeRead"];

const blankToNull = (v: FormDataEntryValue | null) => (v && String(v).trim() ? String(v).trim() : null);

const STATUS_STYLE: Record<Campaign["status"], string> = {
  active: "border-green-300 bg-green-50 text-green-900",
  scheduled: "border-blue-300 bg-blue-50 text-blue-900",
  expired: "border-gray-300 bg-gray-100 text-gray-800",
  exhausted: "border-amber-400 bg-amber-50 text-amber-950",
  disabled: "border-gray-300 bg-gray-100 text-gray-800",
};

/** Promo campaigns and their Campaign QR codes (SRS 4.14). Every number comes from the
 * server; this screen never computes a discount. */
export function CampaignsPanel() {
  const t = useTranslations("organizer.campaigns");
  const tc = useTranslations("common");
  const money = useMoney();
  const errorMessage = useErrorMessage();
  const { event } = useOrganizerEvent();
  // Print the Campaign QR in the language the organizer is using right now.
  const lang = useLocale() as "kk" | "ru" | "en";
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [types, setTypes] = useState<TicketType[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [formError, setFormError] = useState<unknown>(null);
  const [discountType, setDiscountType] = useState<"percentage" | "fixed_kzt">("percentage");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const closed = event.status === "cancelled" || event.status === "completed";

  const load = useCallback(async () => {
    const path = { params: { path: { event_id: event.id } } };
    const [list, ticketTypes] = await Promise.all([
      unwrap(api.GET("/api/v1/organizer/events/{event_id}/campaigns", path)),
      unwrap(api.GET("/api/v1/organizer/events/{event_id}/ticket-types", path)),
    ]);
    return { list, ticketTypes };
  }, [event.id]);

  const refresh = useCallback(async () => {
    try {
      const { list, ticketTypes } = await load();
      setCampaigns(list);
      setTypes(ticketTypes);
    } catch (err) {
      setError(err);
    }
  }, [load]);

  useEffect(() => {
    let active = true;
    load()
      .then(({ list, ticketTypes }) => {
        if (!active) return;
        setCampaigns(list);
        setTypes(ticketTypes);
      })
      .catch((err: unknown) => active && setError(err));
    return () => {
      active = false;
    };
  }, [load]);

  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const max = blankToNull(f.get("max_redemptions"));
    setBusy(true);
    setFormError(null);
    setNotice(null);
    try {
      await unwrap(
        api.POST("/api/v1/organizer/events/{event_id}/campaigns", {
          params: { path: { event_id: event.id } },
          body: {
            name: String(f.get("name") ?? "").trim(),
            description: blankToNull(f.get("description")),
            discount_type: discountType,
            discount_percent: discountType === "percentage" ? Number(f.get("discount_percent")) : null,
            discount_kzt: discountType === "fixed_kzt" ? Number(f.get("discount_kzt")) : null,
            code: blankToNull(f.get("code")),
            // datetime-local values carry no offset: the API reads them in the event's zone.
            starts_at: blankToNull(f.get("starts_at")),
            ends_at: blankToNull(f.get("ends_at")),
            max_redemptions: max === null ? null : Number(max),
            ticket_type_ids: f.getAll("ticket_type_ids").map(String),
          },
        }),
      );
      form.reset();
      setDiscountType("percentage");
      await refresh();
    } catch (err) {
      setFormError(err);
    } finally {
      setBusy(false);
    }
  }

  async function disable(campaign: Campaign) {
    if (!window.confirm(t("disableConfirm"))) return;
    setError(null);
    try {
      await unwrap(
        api.POST("/api/v1/organizer/events/{event_id}/campaigns/{campaign_id}/disable", {
          params: { path: { event_id: event.id, campaign_id: campaign.id } },
        }),
      );
      await refresh();
    } catch (err) {
      setError(err);
    }
  }

  async function download(campaign: Campaign, fmt: "svg" | "pdf") {
    setError(null);
    try {
      await saveDownload(
        api.GET("/api/v1/organizer/events/{event_id}/campaigns/{campaign_id}/qr.{fmt}", {
          params: { path: { event_id: event.id, campaign_id: campaign.id, fmt }, query: { lang } },
          parseAs: "blob",
        }),
        `campaign-qr-${campaign.code}.${fmt}`,
      );
    } catch (err) {
      setError(err);
    }
  }

  async function copyLink(campaign: Campaign) {
    try {
      await navigator.clipboard.writeText(campaign.campaign_url);
      setNotice(t("copied"));
    } catch {
      window.prompt(t("link"), campaign.campaign_url);
    }
  }

  const typeName = (id: string) => types.find((tt) => tt.id === id)?.name ?? "—";
  const fields = formError instanceof ApiError ? formError.fields : {};

  return (
    <div className="space-y-6">
      <p className="text-gray-600">{t("lead")}</p>
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      {notice && <Alert kind="success">{notice}</Alert>}
      {campaigns === null && !error && <p className="text-gray-600">{tc("loading")}</p>}
      {campaigns?.length === 0 && <p className="text-gray-600">{t("empty")}</p>}

      {campaigns && campaigns.length > 0 && (
        <ul className="space-y-4">
          {campaigns.map((c) => (
            <li key={c.id}>
              <Card className="space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <h3 className="text-lg font-semibold text-gray-900">{c.name}</h3>
                    <p className="text-gray-800">
                      <span className="font-mono text-base font-bold tracking-wider">{c.code}</span>
                      {" · "}
                      {c.discount_type === "percentage"
                        ? t("percentOff", { value: c.discount_percent ?? 0 })
                        : t("amountOff", { amount: money(c.discount_kzt ?? 0) })}
                    </p>
                    <p className="text-sm text-gray-600">
                      {c.ticket_type_ids.length === 0 ? t("allTypes") : c.ticket_type_ids.map(typeName).join(", ")}
                      {" · "}
                      {c.max_redemptions === null
                        ? t("used", { count: c.redeemed_count })
                        : t("usedOf", { count: c.redeemed_count, max: c.max_redemptions })}
                    </p>
                  </div>
                  <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[c.status]}`}>
                    <span className="sr-only">{t("statusLabel")}: </span>
                    {t(`status.${c.status}`)}
                  </span>
                </div>

                <div className="grid gap-4 sm:grid-cols-[10rem_1fr]">
                  <CampaignQr eventId={event.id} campaign={c} lang={lang} alt={t("qrAlt", { code: c.code })} label={t("notATicket")} />
                  <div className="space-y-3">
                    <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
                      {(
                        [
                          ["redemptions", String(c.report.redemptions)],
                          ["orders", String(c.report.orders)],
                          ["ticketsSold", String(c.report.tickets_sold)],
                          ["gross", money(c.report.gross_revenue_kzt)],
                          ["discount", money(c.report.discount_kzt)],
                          ["net", money(c.report.net_revenue_kzt)],
                        ] as const
                      ).map(([key, value]) => (
                        <div key={key}>
                          <dt className="text-gray-600">{t(`report.${key}`)}</dt>
                          <dd className="font-medium text-gray-900">{value}</dd>
                        </div>
                      ))}
                    </dl>
                    <p className="flex items-center gap-2 text-xs text-gray-600">
                      <DemoBadge label={tc("demo")} /> {t("demoNote")}
                    </p>
                    <p className="break-all text-sm">
                      <span className="text-gray-600">{t("link")}: </span>
                      <span className="font-mono text-gray-900">{c.campaign_url}</span>
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Button variant="secondary" onClick={() => void copyLink(c)}>
                        {t("copyLink")}
                      </Button>
                      <Button variant="secondary" onClick={() => void download(c, "svg")}>
                        {t("downloadSvg")}
                      </Button>
                      <Button variant="secondary" onClick={() => void download(c, "pdf")}>
                        {t("downloadPdf")}
                      </Button>
                      {c.status !== "disabled" && (
                        <Button variant="danger" onClick={() => void disable(c)}>
                          {t("disable")}
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      {!closed && (
        <Card>
          <h2 className="mb-4 text-lg font-semibold text-gray-900">{t("add")}</h2>
          <form onSubmit={create} className="grid gap-4 sm:grid-cols-2" noValidate>
            {formError ? (
              <div className="sm:col-span-2">
                <Alert kind="error">{errorMessage(formError)}</Alert>
              </div>
            ) : null}
            <Field name="name" label={t("name")} required maxLength={200} error={fields.name && errorMessage(formError)} />
            <Field
              name="code"
              label={`${t("code")} (${tc("optional")})`}
              hint={t("codeHint")}
              maxLength={40}
              pattern="[A-Za-z0-9][A-Za-z0-9-]{2,39}"
              autoCapitalize="characters"
              error={fields.code && errorMessage(formError)}
            />
            <Select
              label={t("discountType")}
              value={discountType}
              onChange={(e) => setDiscountType(e.target.value as "percentage" | "fixed_kzt")}
              options={[
                { value: "percentage", label: t("percentage") },
                { value: "fixed_kzt", label: t("fixed") },
              ]}
            />
            {discountType === "percentage" ? (
              <Field name="discount_percent" type="number" min={1} max={100} step={1} label={t("percent")} defaultValue={10} required />
            ) : (
              <Field name="discount_kzt" type="number" min={1} step={1} label={t("amount")} defaultValue={1000} required />
            )}
            <Field
              name="starts_at"
              type="datetime-local"
              label={`${t("startsAt")} (${tc("optional")})`}
              hint={t("datesHint", { timezone: event.timezone })}
            />
            <Field name="ends_at" type="datetime-local" label={`${t("endsAt")} (${tc("optional")})`} />
            <Field
              name="max_redemptions"
              type="number"
              min={1}
              step={1}
              label={`${t("maxRedemptions")} (${tc("optional")})`}
              hint={t("maxRedemptionsHint")}
            />
            <Field name="description" label={`${t("description")} (${tc("optional")})`} maxLength={2000} />
            {types.length > 0 && (
              <fieldset className="sm:col-span-2">
                <legend className="mb-1 text-sm font-medium text-gray-900">{t("eligibleTypes")}</legend>
                <p className="mb-2 text-sm text-gray-600">{t("eligibleHint")}</p>
                <div className="flex flex-wrap gap-4">
                  {types.map((tt) => (
                    <label key={tt.id} className="flex items-center gap-2 text-sm text-gray-900">
                      <input type="checkbox" name="ticket_type_ids" value={tt.id} className="h-4 w-4" />
                      {tt.name}
                    </label>
                  ))}
                </div>
              </fieldset>
            )}
            <div className="sm:col-span-2">
              <Button type="submit" disabled={busy}>
                {t("create")}
              </Button>
            </div>
          </form>
        </Card>
      )}
    </div>
  );
}

/** The Campaign QR as the API draws it: purple, dashed frame, "PROMO · NOT A TICKET". */
function CampaignQr({
  eventId,
  campaign,
  lang,
  alt,
  label,
}: {
  eventId: string;
  campaign: Campaign;
  lang: "kk" | "ru" | "en";
  alt: string;
  label: string;
}) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    api
      .GET("/api/v1/organizer/events/{event_id}/campaigns/{campaign_id}/qr.{fmt}", {
        params: { path: { event_id: eventId, campaign_id: campaign.id, fmt: "svg" }, query: { lang } },
        parseAs: "text",
      })
      .then(({ data }) => {
        if (active && typeof data === "string") {
          setSrc(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(data)}`);
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [eventId, campaign.id, lang]);
  return (
    <figure className="w-40">
      <div className="flex aspect-[3/4] items-center justify-center rounded-md border border-dashed border-violet-500 bg-white">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element -- inline SVG data URL
          <img src={src} alt={alt} className="h-full w-full object-contain" />
        ) : null}
      </div>
      <figcaption className="mt-1 text-center text-xs font-semibold uppercase tracking-wide text-violet-800">
        {label}
      </figcaption>
    </figure>
  );
}
