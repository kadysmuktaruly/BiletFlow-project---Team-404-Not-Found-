"use client";

import type { Schemas } from "@biletflow/api-types";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useId, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Alert, DemoBadge, Field, Select } from "@/components/ui";
import { api, unwrap } from "@/lib/api";
import { useMoney } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

type Analytics = Schemas["AnalyticsRead"];
type Metric = "tickets" | "revenue";

// Single-series charts: categorical slot 1 of the validated reference palette. Text stays in
// the page's ink colors, never the series color; grid and axes are recessive.
// Chart colours mirror the design tokens in app/globals.css (Recharts needs literal values).
const SERIES = "#00677f"; // sky-ink
const GRID = "#d5d9e0"; // line
const AXIS_TEXT = "#4a5260"; // ink-muted

/**
 * SRS 4.15 dashboard: KPI tiles, a line chart of sales over time, a bar chart by ticket
 * type, campaigns and attendance. Every chart has a table view. With `eventId` it's scoped
 * to one event (the event's Analytics tab); without it the organizer picks.
 */
export function AnalyticsDashboard({ eventId }: { eventId?: string }) {
  const t = useTranslations("analytics");
  const tc = useTranslations("common");
  const money = useMoney();
  const errorMessage = useErrorMessage();
  const [event, setEvent] = useState(eventId ?? "");
  const [ticketType, setTicketType] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [events, setEvents] = useState<Schemas["EventRead"][]>([]);
  const [result, setResult] = useState<{ key: string; data?: Analytics; error?: unknown } | null>(null);
  const key = `${event}|${ticketType}|${from}|${to}`;

  useEffect(() => {
    if (eventId) return;
    let active = true;
    unwrap(api.GET("/api/v1/organizer/events"))
      .then((list) => active && setEvents(list))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [eventId]);

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      unwrap(
        api.GET("/api/v1/organizer/analytics", {
          params: {
            query: {
              event_id: event || null,
              ticket_type_id: ticketType || null,
              date_from: from || null,
              date_to: to || null,
            },
          },
        }),
      )
        .then((data) => active && setResult({ key, data }))
        .catch((error: unknown) => active && setResult({ key, error }));
    }, 200);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [key, event, ticketType, from, to]);

  const data = result?.data;
  // The ticket types of the chosen event, for the type filter.
  const [types, setTypes] = useState<{ event: string; options: { value: string; label: string }[] } | null>(null);
  useEffect(() => {
    if (!event) return;
    let active = true;
    unwrap(api.GET("/api/v1/organizer/events/{event_id}/ticket-types", { params: { path: { event_id: event } } }))
      .then((list) => active && setTypes({ event, options: list.map((tt) => ({ value: tt.id, label: tt.name })) }))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [event]);
  const typeOptions = types?.event === event ? types.options : [];

  return (
    <div className="space-y-6">
      <p className="flex flex-wrap items-center gap-2 text-ink-muted">
        <DemoBadge label={tc("demo")} /> {t("lead")}
      </p>

      {/* Filters: one row above the charts. */}
      <div className="flex flex-wrap items-end gap-3">
        {!eventId && (
          <Select
            label={t("event")}
            value={event}
            onChange={(e) => {
              setEvent(e.target.value);
              setTicketType("");
            }}
            options={[{ value: "", label: t("allEvents") }, ...events.map((e) => ({ value: e.id, label: e.title }))]}
          />
        )}
        {event && (
          <Select
            label={t("ticketType")}
            value={ticketType}
            onChange={(e) => setTicketType(e.target.value)}
            options={[{ value: "", label: t("allTypes") }, ...typeOptions]}
          />
        )}
        <Field type="date" label={t("from")} value={from || data?.filters.date_from || ""} onChange={(e) => setFrom(e.target.value)} />
        <Field type="date" label={t("to")} value={to || data?.filters.date_to || ""} onChange={(e) => setTo(e.target.value)} />
      </div>
      {result?.error ? <Alert kind="error">{errorMessage(result.error)}</Alert> : null}
      {!data && !result?.error && <p className="text-ink-muted">{tc("loading")}</p>}

      {data && (
        <>
          <p className="text-sm text-ink-muted">{t("rangeNote", { timezone: data.filters.timezone })}</p>
          <Kpis data={data} />
          <SalesOverTime data={data} />
          <ByTicketType data={data} />
          <Campaigns data={data} money={money} />
        </>
      )}
    </div>
  );
}

function Kpis({ data }: { data: Analytics }) {
  const t = useTranslations("analytics.kpi");
  const money = useMoney();
  const { capacity, revenue, attendance } = data;
  const tiles: { label: string; value: string; note?: string }[] = [
    {
      label: t("sold"),
      value: t("soldOf", { sold: capacity.sold, capacity: capacity.capacity, percent: capacity.percent_sold }),
      note: t("remaining", { count: capacity.remaining }),
    },
    { label: t("gross"), value: money(revenue.gross_kzt) },
    { label: t("discounts"), value: money(revenue.discounts_kzt) },
    { label: t("refunds"), value: money(revenue.refunds_kzt) },
    { label: t("net"), value: money(revenue.net_kzt) },
    { label: t("fees"), value: money(revenue.processing_fees_kzt) },
    { label: t("payout"), value: money(revenue.estimated_payout_kzt) },
    {
      label: t("checkedIn"),
      value: t("checkedInOf", { checkedIn: attendance.checked_in, issued: attendance.issued, percent: attendance.percent_checked_in }),
      note: t("absent", { count: attendance.absent }),
    },
  ];
  return (
    <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tiles.map((tile) => (
        <div key={tile.label} className="rounded-card border border-line bg-surface p-4">
          <dt className="text-sm text-ink-muted">{tile.label}</dt>
          <dd className="font-display mt-1 text-2xl text-ink tabular-nums">{tile.value}</dd>
          {tile.note && <dd className="text-sm text-ink-muted">{tile.note}</dd>}
        </div>
      ))}
    </dl>
  );
}

function TableToggle({ open, onToggle, controls }: { open: boolean; onToggle: () => void; controls: string }) {
  const t = useTranslations("analytics");
  return (
    <button type="button" onClick={onToggle} aria-expanded={open} aria-controls={controls} className="text-sm font-semibold text-sky-ink underline decoration-1 underline-offset-4 hover:decoration-2">
      {open ? t("hideTable") : t("showTable")}
    </button>
  );
}

function SalesOverTime({ data }: { data: Analytics }) {
  const t = useTranslations("analytics");
  const money = useMoney();
  const format = useFormatter();
  const id = useId();
  const [metric, setMetric] = useState<Metric>("tickets");
  const [table, setTable] = useState(false);
  const points = data.sales_over_time.map((p) => ({ ...p, value: metric === "tickets" ? p.tickets : p.revenue_kzt }));
  const total = points.reduce((sum, p) => sum + p.value, 0);
  const day = (iso: string) => format.dateTime(new Date(`${iso}T12:00:00`), { day: "numeric", month: "short" });
  const show = (v: number) => (metric === "tickets" ? String(v) : money(v));
  const summary =
    metric === "tickets"
      ? t("chartSummaryTickets", { total, days: points.length })
      : t("chartSummaryRevenue", { total: money(total), days: points.length });

  return (
    <section aria-labelledby={`${id}-title`} className="space-y-3 rounded-card border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={`${id}-title`} className="font-display text-xl text-ink">
          {t("overTime")}
        </h2>
        {/* One measure at a time: tickets and money never share a y-axis. */}
        <fieldset className="flex items-center gap-1 text-sm">
          <legend className="sr-only">{t("metric")}</legend>
          {(["tickets", "revenue"] as const).map((m) => (
            <label key={m} className={`inline-flex min-h-9 cursor-pointer items-center rounded-full border px-3.5 font-semibold has-[:focus-visible]:outline has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-sky-ink ${metric === m ? "border-ink bg-ink text-surface" : "border-line-strong bg-surface text-ink"}`}>
              <input type="radio" name={`${id}-metric`} value={m} checked={metric === m} onChange={() => setMetric(m)} className="sr-only" />
              {t(m)}
            </label>
          ))}
        </fieldset>
      </div>
      <p className="text-sm text-ink-muted">{summary}</p>
      <div className="h-64" role="img" aria-label={`${t("overTime")}. ${summary}`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="date" tickFormatter={day} tick={{ fill: AXIS_TEXT, fontSize: 12 }} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={24} />
            <YAxis allowDecimals={false} tickFormatter={(v: number) => (metric === "tickets" ? String(v) : format.number(v, { notation: "compact" }))} tick={{ fill: AXIS_TEXT, fontSize: 12 }} tickLine={false} axisLine={false} width={56} />
            <Tooltip
              cursor={{ stroke: AXIS_TEXT, strokeDasharray: "3 3" }}
              formatter={(v) => [show(Number(v)), t(metric)]}
              labelFormatter={(label) => day(String(label))}
              contentStyle={{ borderRadius: 12, borderColor: GRID, color: "#101418" }}
              itemStyle={{ color: "#101418" }}
            />
            <Line type="linear" dataKey="value" name={t(metric)} stroke={SERIES} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" dot={false} activeDot={{ r: 5, stroke: "#ffffff", strokeWidth: 2 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <TableToggle open={table} onToggle={() => setTable((v) => !v)} controls={`${id}-table`} />
      {table && (
        <div id={`${id}-table`} className="max-h-72 overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 bg-surface text-left text-ink-muted">
              <tr>
                <th scope="col" className="py-1 pr-4">{t("date")}</th>
                <th scope="col" className="py-1 pr-4 text-right">{t("tickets")}</th>
                <th scope="col" className="py-1 text-right">{t("revenue")}</th>
              </tr>
            </thead>
            <tbody className="text-ink">
              {data.sales_over_time.map((p) => (
                <tr key={p.date} className="border-t border-line">
                  <th scope="row" className="py-1 pr-4 text-left font-normal">{day(p.date)}</th>
                  <td className="py-1 pr-4 text-right">{p.tickets}</td>
                  <td className="py-1 text-right">{money(p.revenue_kzt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function ByTicketType({ data }: { data: Analytics }) {
  const t = useTranslations("analytics");
  const money = useMoney();
  const id = useId();
  const rows = data.by_ticket_type;
  const height = Math.max(120, rows.length * 44 + 32);
  return (
    <section aria-labelledby={`${id}-title`} className="space-y-3 rounded-card border border-line bg-surface p-5">
      <h2 id={`${id}-title`} className="font-display text-xl text-ink">
        {t("byType")}
      </h2>
      {rows.length === 0 ? (
        <p className="text-ink-muted">{t("noData")}</p>
      ) : (
        <>
          <div style={{ height }} role="img" aria-label={`${t("byType")}: ${rows.map((r) => `${r.name} ${r.tickets_in_range}`).join(", ")}`}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 48, bottom: 4, left: 8 }} barCategoryGap={12}>
                <CartesianGrid horizontal={false} stroke={GRID} />
                <XAxis type="number" allowDecimals={false} tick={{ fill: AXIS_TEXT, fontSize: 12 }} tickLine={false} axisLine={{ stroke: GRID }} />
                <YAxis type="category" dataKey="name" width={120} tick={{ fill: "#101418", fontSize: 13 }} tickLine={false} axisLine={false} />
                <Tooltip
                  cursor={{ fill: "#eef0f3" }}
                  formatter={(v, _name, item) => [`${v} · ${money((item.payload as { revenue_kzt: number }).revenue_kzt)}`, t("inRange")]}
                  contentStyle={{ borderRadius: 12, borderColor: GRID, color: "#101418" }}
              itemStyle={{ color: "#101418" }}
                />
                <Bar dataKey="tickets_in_range" name={t("inRange")} fill={SERIES} barSize={20} radius={[0, 4, 4, 0]} isAnimationActive={false}>
                  <LabelList dataKey="tickets_in_range" position="right" fill="#101418" fontSize={12} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-ink-muted">
                <tr>
                  <th scope="col" className="py-1 pr-4">{t("name")}</th>
                  <th scope="col" className="py-1 pr-4 text-right">{t("inRange")}</th>
                  <th scope="col" className="py-1 pr-4 text-right">{t("revenue")}</th>
                  <th scope="col" className="py-1 pr-4 text-right">{t("soldNow")}</th>
                  <th scope="col" className="py-1 pr-4 text-right">{t("capacity")}</th>
                  <th scope="col" className="py-1 text-right">{t("checked")}</th>
                </tr>
              </thead>
              <tbody className="text-ink">
                {rows.map((r) => (
                  <tr key={r.ticket_type_id} className="border-t border-line">
                    <th scope="row" className="py-1 pr-4 text-left font-medium">{r.name}</th>
                    <td className="py-1 pr-4 text-right">{r.tickets_in_range}</td>
                    <td className="py-1 pr-4 text-right">{money(r.revenue_kzt)}</td>
                    <td className="py-1 pr-4 text-right">{r.sold}</td>
                    <td className="py-1 pr-4 text-right">{r.capacity}</td>
                    <td className="py-1 text-right">{r.checked_in}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

function Campaigns({ data, money }: { data: Analytics; money: (n: number) => string }) {
  const t = useTranslations("analytics");
  const id = useId();
  return (
    <section aria-labelledby={`${id}-title`} className="space-y-3 rounded-card border border-line bg-surface p-5">
      <h2 id={`${id}-title`} className="font-display text-xl text-ink">
        {t("campaigns")}
      </h2>
      {data.campaigns.length === 0 ? (
        <p className="text-ink-muted">{t("noCampaigns")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-ink-muted">
              <tr>
                {(["campaign", "code", "redemptions", "orders", "tickets", "gross", "discount", "net"] as const).map((c, i) => (
                  <th key={c} scope="col" className={`py-1 pr-4 ${i > 1 ? "text-right" : ""}`}>{t(c)}</th>
                ))}
              </tr>
            </thead>
            <tbody className="text-ink">
              {data.campaigns.map((c) => (
                <tr key={c.campaign_id} className="border-t border-line">
                  <th scope="row" className="py-1 pr-4 text-left font-medium">{c.name}</th>
                  <td className="py-1 pr-4 font-mono">{c.code ?? "—"}</td>
                  <td className="py-1 pr-4 text-right">{c.redemptions}</td>
                  <td className="py-1 pr-4 text-right">{c.orders}</td>
                  <td className="py-1 pr-4 text-right">{c.tickets}</td>
                  <td className="py-1 pr-4 text-right">{money(c.gross_kzt)}</td>
                  <td className="py-1 pr-4 text-right">{money(c.discount_kzt)}</td>
                  <td className="py-1 pr-4 text-right">{money(c.net_kzt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
