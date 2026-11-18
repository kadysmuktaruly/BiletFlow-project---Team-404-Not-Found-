"use client";

import type { Schemas } from "@biletflow/api-types";
import { useFormatter, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { Alert, Button, Card, DemoBadge, EmptyState, Field, PageTitle, Select, TAB_BAR, tabClass, Toast } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { saveDownload } from "@/lib/download";
import { useMoney } from "@/lib/format";
import { useErrorMessage } from "@/lib/use-error-message";

const TABS = ["overview", "users", "events", "orders", "payments", "activations", "reports", "settings"] as const;
type Tab = (typeof TABS)[number];

/** The Platform Admin portal (SRS 4.12). The API enforces the role; tabs live in `?tab=`. */
export function AdminPortal() {
  const t = useTranslations("admin");
  const search = useSearchParams();
  const requested = search.get("tab");
  const tab: Tab = TABS.includes(requested as Tab) ? (requested as Tab) : "overview";

  return (
    <div className="space-y-6">
      <PageTitle>{t("title")}</PageTitle>
      <nav aria-label={t("title")} className="border-b border-line pb-3">
        <ul className={TAB_BAR}>
          {TABS.map((name) => (
            <li key={name}>
              <Link
                href={{ pathname: "/admin", query: { tab: name } }}
                aria-current={tab === name ? "page" : undefined}
                className={tabClass(tab === name)}
              >
                {t(`tabs.${name}`)}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      {tab === "overview" && <Overview />}
      {tab === "users" && <Users />}
      {tab === "events" && <Events />}
      {tab === "orders" && <Orders />}
      {tab === "payments" && <Payments />}
      {tab === "activations" && <Activations />}
      {tab === "reports" && <Reports />}
      {tab === "settings" && <Settings />}
    </div>
  );
}

// --- shared --------------------------------------------------------------------------------

/** Fetch a list whenever its inputs change (debounced), and on demand after an action. */
function useList<T>(fetcher: () => Promise<T>, key: string): { data: T | null; error: unknown; reload: () => void } {
  const [state, setState] = useState<{ key: string; data?: T; error?: unknown } | null>(null);
  const [tick, setTick] = useState(0);
  const fullKey = `${key}|${tick}`;
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      fetcher()
        .then((data) => active && setState({ key: fullKey, data }))
        .catch((error: unknown) => active && setState({ key: fullKey, error }));
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
    // `fetcher` is rebuilt each render; `key` captures everything it depends on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fullKey]);
  return { data: state?.data ?? null, error: state?.error ?? null, reload: () => setTick((n) => n + 1) };
}

function Toolbar({ query, setQuery, children, exportKind }: {
  query: string;
  setQuery: (q: string) => void;
  children?: React.ReactNode;
  exportKind?: "users" | "events" | "orders" | "payments";
}) {
  const t = useTranslations("admin");
  const errorMessage = useErrorMessage();
  const [error, setError] = useState<unknown>(null);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end gap-3">
        <Field className="min-w-60 flex-1" type="search" label={t("search")} value={query} onChange={(e) => setQuery(e.target.value)} maxLength={200} />
        {children}
        {exportKind && (
          <Button
            variant="secondary"
            onClick={() =>
              void saveDownload(
                api.GET("/api/v1/admin/export/{kind}.csv", { params: { path: { kind: exportKind } }, parseAs: "blob" }),
                `biletflow-${exportKind}.csv`,
              ).catch(setError)
            }
          >
            {t("exportCsv")}
          </Button>
        )}
      </div>
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
    </div>
  );
}

function Table({ head, children, empty }: { head: string[]; children: React.ReactNode; empty: boolean }) {
  const t = useTranslations("admin");
  if (empty) return <EmptyState>{t("empty")}</EmptyState>;
  return (
    <div className="overflow-x-auto rounded-card border border-line bg-surface">
      <table className="min-w-full divide-y divide-line text-sm">
        <thead className="bg-paper text-left text-[0.8125rem] text-ink-muted">
          <tr>
            {head.map((h) => (
              <th key={h} scope="col" className="px-3 py-2 font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line text-ink">{children}</tbody>
      </table>
    </div>
  );
}

function ListState({ error, loading, truncated }: { error: unknown; loading: boolean; truncated?: boolean }) {
  const t = useTranslations("admin");
  const tc = useTranslations("common");
  const errorMessage = useErrorMessage();
  if (error) return <Alert kind="error">{errorMessage(error)}</Alert>;
  if (loading) return <p className="text-ink-muted">{tc("loading")}</p>;
  return truncated ? <p className="text-sm text-ink-muted">{t("truncated")}</p> : null;
}

type Pending = { title: string; text: string; confirm: string; reasonRequired?: boolean; run: (reason: string | null) => Promise<unknown> };

/** Runs an admin action behind a confirmation; shows the API's error if it fails. */
function useConfirm(onDone: () => void) {
  const t = useTranslations("admin.confirm");
  const errorMessage = useErrorMessage();
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const dialog = pending ? (
    <div className="space-y-2">
      {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
      <ConfirmDialog
        title={pending.title}
        text={pending.text}
        reasonLabel={pending.reasonRequired ? t("reason") : t("note")}
        reasonRequired={pending.reasonRequired}
        confirmLabel={pending.confirm}
        cancelLabel={t("keep")}
        busy={busy}
        onCancel={() => setPending(null)}
        onConfirm={async (reason) => {
          setBusy(true);
          setError(null);
          try {
            await pending.run(reason);
            setPending(null);
            onDone();
          } catch (err) {
            setError(err);
          } finally {
            setBusy(false);
          }
        }}
      />
    </div>
  ) : null;
  return { dialog, ask: (p: Pending) => (setError(null), setPending(p)) };
}

// --- tabs ----------------------------------------------------------------------------------

function Overview() {
  const t = useTranslations("admin.summary");
  const { data, error } = useList(() => unwrap(api.GET("/api/v1/admin/summary")), "summary");
  if (!data) return <ListState error={error} loading={!error} />;
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {(Object.keys(data) as (keyof typeof data)[]).map((key) => (
        <div key={key} className="rounded-card border border-line bg-surface p-4">
          <dt className="text-sm text-ink-muted">{t(key)}</dt>
          <dd className="font-display mt-1 text-3xl text-ink tabular-nums">{data[key]}</dd>
        </div>
      ))}
    </dl>
  );
}

function Users() {
  const t = useTranslations("admin");
  const format = useFormatter();
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<Schemas["UserRole"] | "">("");
  const list = useList(
    () => unwrap(api.GET("/api/v1/admin/users", { params: { query: { q: query.trim() || null, role: role || null } } })),
    `${query}|${role}`,
  );
  const { dialog, ask } = useConfirm(list.reload);
  const roles: Schemas["UserRole"][] = ["attendee", "organizer", "platform_admin"];
  return (
    <div className="space-y-4">
      <Toolbar query={query} setQuery={setQuery} exportKind="users">
        <Select label={t("col.role")} value={role} onChange={(e) => setRole(e.target.value as Schemas["UserRole"] | "")} options={[{ value: "", label: t("all") }, ...roles.map((r) => ({ value: r, label: t(`role.${r}`) }))]} />
      </Toolbar>
      {dialog}
      {list.data && (
        <Table head={[t("col.name"), t("col.email"), t("col.role"), t("col.status"), t("col.created"), t("col.actions")]} empty={list.data.items.length === 0}>
          {list.data.items.map((u) => (
            <tr key={u.id}>
              <th scope="row" className="px-3 py-2 text-left font-medium">{u.full_name}</th>
              <td className="px-3 py-2">{u.email}</td>
              <td className="px-3 py-2">{t(`role.${u.role}`)}</td>
              <td className="px-3 py-2">{u.is_suspended ? t("suspended") : t("active")}</td>
              <td className="px-3 py-2">{format.dateTime(new Date(u.created_at), { dateStyle: "short" })}</td>
              <td className="px-3 py-2">
                {u.role !== "platform_admin" &&
                  (u.is_suspended ? (
                    <Button variant="secondary" onClick={() => void unwrap(api.POST("/api/v1/admin/users/{user_id}/unsuspend", { params: { path: { user_id: u.id } } })).then(list.reload)}>
                      {t("reinstate")}
                    </Button>
                  ) : (
                    <Button
                      variant="secondary"
                      onClick={() =>
                        ask({
                          title: t("confirm.userTitle", { name: u.full_name }),
                          text: t("confirm.userText"),
                          confirm: t("suspend"),
                          reasonRequired: true,
                          run: (reason) => unwrap(api.POST("/api/v1/admin/users/{user_id}/suspend", { params: { path: { user_id: u.id } }, body: { reason: reason ?? "" } })),
                        })
                      }
                    >
                      {t("suspend")}
                    </Button>
                  ))}
              </td>
            </tr>
          ))}
        </Table>
      )}
      <ListState error={list.error} loading={!list.data && !list.error} truncated={list.data?.truncated} />
    </div>
  );
}

function Events() {
  const t = useTranslations("admin");
  const te = useTranslations("event.status");
  const ta = useTranslations("organizer.activation.status");
  const format = useFormatter();
  const [query, setQuery] = useState("");
  const list = useList(() => unwrap(api.GET("/api/v1/admin/events", { params: { query: { q: query.trim() || null } } })), query);
  const { dialog, ask } = useConfirm(list.reload);
  return (
    <div className="space-y-4">
      <Toolbar query={query} setQuery={setQuery} exportKind="events" />
      {dialog}
      {list.data && (
        <Table head={[t("col.event"), t("col.organizer"), t("col.status"), t("col.starts"), t("col.paidSales"), t("col.reports"), t("col.actions")]} empty={list.data.items.length === 0}>
          {list.data.items.map((e) => (
            <tr key={e.id}>
              <th scope="row" className="px-3 py-2 text-left font-medium">
                <Link href={`/events/${e.slug}`} className="font-semibold text-sky-ink underline decoration-1 underline-offset-4 hover:decoration-2">{e.title}</Link>
              </th>
              <td className="px-3 py-2">{e.organizer_name}<span className="block text-xs text-ink-muted">{e.organizer_email}</span></td>
              <td className="px-3 py-2">{te(e.status)}{e.is_suspended && <span className="block text-xs font-semibold text-danger">{t("suspended")}</span>}</td>
              <td className="px-3 py-2">{format.dateTime(new Date(e.starts_at), { dateStyle: "short" })}</td>
              <td className="px-3 py-2">{e.paid_sales ? ta(e.paid_sales) : "—"}</td>
              <td className="px-3 py-2">{e.open_reports}</td>
              <td className="space-y-1 px-3 py-2">
                {e.is_suspended ? (
                  <Button variant="secondary" onClick={() => void unwrap(api.POST("/api/v1/admin/events/{event_id}/unsuspend", { params: { path: { event_id: e.id } } })).then(list.reload)}>
                    {t("reinstate")}
                  </Button>
                ) : (
                  <Button variant="secondary" onClick={() => ask({ title: t("confirm.eventTitle", { title: e.title }), text: t("confirm.eventText"), confirm: t("suspend"), reasonRequired: true, run: (reason) => unwrap(api.POST("/api/v1/admin/events/{event_id}/suspend", { params: { path: { event_id: e.id } }, body: { reason: reason ?? "" } })) })}>
                    {t("suspend")}
                  </Button>
                )}
                {e.paid_sales === "suspended" ? (
                  <Button variant="secondary" onClick={() => void unwrap(api.POST("/api/v1/admin/events/{event_id}/paid-sales/resume", { params: { path: { event_id: e.id } } })).then(list.reload)}>
                    {t("resumeSales")}
                  </Button>
                ) : e.paid_sales ? (
                  <Button variant="secondary" onClick={() => ask({ title: t("confirm.salesTitle", { title: e.title }), text: t("confirm.salesText"), confirm: t("suspendSales"), reasonRequired: true, run: (reason) => unwrap(api.POST("/api/v1/admin/events/{event_id}/paid-sales/suspend", { params: { path: { event_id: e.id } }, body: { reason: reason ?? "" } })) })}>
                    {t("suspendSales")}
                  </Button>
                ) : null}
              </td>
            </tr>
          ))}
        </Table>
      )}
      <ListState error={list.error} loading={!list.data && !list.error} truncated={list.data?.truncated} />
    </div>
  );
}

function Orders() {
  const t = useTranslations("admin");
  const to = useTranslations("order.status");
  const money = useMoney();
  const format = useFormatter();
  const [query, setQuery] = useState("");
  const list = useList(() => unwrap(api.GET("/api/v1/admin/orders", { params: { query: { q: query.trim() || null } } })), query);
  return (
    <div className="space-y-4">
      <Toolbar query={query} setQuery={setQuery} exportKind="orders" />
      {list.data && (
        <Table head={[t("col.reference"), t("col.event"), t("col.buyer"), t("col.amount"), t("col.status"), t("col.created")]} empty={list.data.items.length === 0}>
          {list.data.items.map((o) => (
            <tr key={o.id}>
              <th scope="row" className="px-3 py-2 text-left font-mono font-medium">{o.reference}</th>
              <td className="px-3 py-2">{o.event_title}</td>
              <td className="px-3 py-2">{o.buyer_email}</td>
              <td className="px-3 py-2">{money(o.total_kzt)}{o.refunded_kzt > 0 && <span className="block text-xs text-ink-muted">−{money(o.refunded_kzt)}</span>}</td>
              <td className="px-3 py-2">{to(o.status)}</td>
              <td className="px-3 py-2">{format.dateTime(new Date(o.created_at), { dateStyle: "short", timeStyle: "short" })}</td>
            </tr>
          ))}
        </Table>
      )}
      <ListState error={list.error} loading={!list.data && !list.error} truncated={list.data?.truncated} />
    </div>
  );
}

function Payments() {
  const t = useTranslations("admin");
  const tc = useTranslations("common");
  const money = useMoney();
  const format = useFormatter();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<Schemas["PaymentStatus"] | "">("");
  const list = useList(
    () => unwrap(api.GET("/api/v1/admin/payments", { params: { query: { q: query.trim() || null, status: status || null } } })),
    `${query}|${status}`,
  );
  const statuses: Schemas["PaymentStatus"][] = ["succeeded", "failed", "refunded", "pending"];
  return (
    <div className="space-y-4">
      <p className="flex items-center gap-2 text-sm text-ink-muted"><DemoBadge label={tc("demo")} /> {t("demoNote")}</p>
      <Toolbar query={query} setQuery={setQuery} exportKind="payments">
        <Select label={t("col.status")} value={status} onChange={(e) => setStatus(e.target.value as Schemas["PaymentStatus"] | "")} options={[{ value: "", label: t("all") }, ...statuses.map((s) => ({ value: s, label: t(`paymentStatus.${s}`) }))]} />
      </Toolbar>
      {list.data && (
        <Table head={[t("col.purpose"), t("col.status"), t("col.amount"), t("col.buyer"), t("col.event"), t("col.reference"), t("col.created")]} empty={list.data.items.length === 0}>
          {list.data.items.map((p) => (
            <tr key={p.id}>
              <th scope="row" className="px-3 py-2 text-left font-medium">{t(`purpose.${p.purpose}`)}</th>
              <td className="px-3 py-2">{t(`paymentStatus.${p.status}`)}{p.failure_reason && <span className="block text-xs text-ink-muted">{p.failure_reason}</span>}</td>
              <td className="px-3 py-2">{money(p.amount_kzt)}</td>
              <td className="px-3 py-2">{p.user_email}</td>
              <td className="px-3 py-2">{p.event_title ?? "—"}</td>
              <td className="px-3 py-2 font-mono text-xs">{p.order_reference ?? p.provider_reference ?? "—"}</td>
              <td className="px-3 py-2">{format.dateTime(new Date(p.created_at), { dateStyle: "short", timeStyle: "short" })}</td>
            </tr>
          ))}
        </Table>
      )}
      <ListState error={list.error} loading={!list.data && !list.error} truncated={list.data?.truncated} />
    </div>
  );
}

function Activations() {
  const t = useTranslations("admin");
  const ta = useTranslations("organizer.activation.status");
  const money = useMoney();
  const [query, setQuery] = useState("");
  const list = useList(() => unwrap(api.GET("/api/v1/admin/activations", { params: { query: { q: query.trim() || null } } })), query);
  return (
    <div className="space-y-4">
      <Toolbar query={query} setQuery={setQuery} />
      {list.data && (
        <Table head={[t("col.event"), t("col.organizer"), t("col.status"), t("col.checklist"), t("col.fee"), t("col.reason")]} empty={list.data.items.length === 0}>
          {list.data.items.map((a) => {
            const steps = [a.has_paid_ticket_type, a.identity_verified, a.payout_account_connected, a.activation_fee_paid, a.terms_accepted];
            return (
              <tr key={a.event_id}>
                <th scope="row" className="px-3 py-2 text-left font-medium">{a.event_title}</th>
                <td className="px-3 py-2">{a.organizer_name}</td>
                <td className="px-3 py-2">{ta(a.status)}</td>
                <td className="px-3 py-2">{steps.filter(Boolean).length} / {steps.length}</td>
                <td className="px-3 py-2">{a.activation_fee_paid ? money(a.activation_fee_kzt) : "—"}</td>
                <td className="px-3 py-2">{a.suspended_reason ?? "—"}</td>
              </tr>
            );
          })}
        </Table>
      )}
      <ListState error={list.error} loading={!list.data && !list.error} truncated={list.data?.truncated} />
    </div>
  );
}

function Reports() {
  const t = useTranslations("admin");
  const tr = useTranslations("report.reasons");
  const format = useFormatter();
  const [status, setStatus] = useState<Schemas["EventReportStatus"] | "">("open");
  const list = useList(() => unwrap(api.GET("/api/v1/admin/reports", { params: { query: { status: status || null } } })), status);
  const { dialog, ask } = useConfirm(list.reload);
  const statuses: Schemas["EventReportStatus"][] = ["open", "dismissed", "actioned"];
  const review = (id: string, action: "dismiss" | "suspend_event") => (note: string | null) =>
    unwrap(api.POST("/api/v1/admin/reports/{report_id}/review", { params: { path: { report_id: id } }, body: { action, note } }));
  return (
    <div className="space-y-4">
      <Select className="max-w-xs" label={t("col.status")} value={status} onChange={(e) => setStatus(e.target.value as Schemas["EventReportStatus"] | "")} options={[{ value: "", label: t("all") }, ...statuses.map((s) => ({ value: s, label: t(`reportStatus.${s}`) }))]} />
      {dialog}
      {list.data && (
        <Table head={[t("col.event"), t("col.reason"), t("col.reporter"), t("col.status"), t("col.created"), t("col.actions")]} empty={list.data.items.length === 0}>
          {list.data.items.map((r) => (
            <tr key={r.id}>
              <th scope="row" className="px-3 py-2 text-left font-medium">
                <Link href={`/events/${r.event_slug}`} className="font-semibold text-sky-ink underline decoration-1 underline-offset-4 hover:decoration-2">{r.event_title}</Link>
                {r.event_suspended && <span className="block text-xs font-semibold text-danger">{t("suspended")}</span>}
              </th>
              <td className="px-3 py-2">{tr(r.reason)}{r.details && <span className="block text-xs text-ink-muted">{r.details}</span>}</td>
              <td className="px-3 py-2">{r.reporter_email}</td>
              <td className="px-3 py-2">{t(`reportStatus.${r.status}`)}{r.review_note && <span className="block text-xs text-ink-muted">{r.review_note}</span>}</td>
              <td className="px-3 py-2">{format.dateTime(new Date(r.created_at), { dateStyle: "short", timeStyle: "short" })}</td>
              <td className="space-y-1 px-3 py-2">
                {r.status === "open" && (
                  <>
                    <Button variant="secondary" onClick={() => ask({ title: t("confirm.dismissTitle"), text: t("confirm.dismissText"), confirm: t("dismiss"), run: review(r.id, "dismiss") })}>{t("dismiss")}</Button>
                    <Button variant="secondary" onClick={() => ask({ title: t("confirm.actionTitle"), text: t("confirm.actionText"), confirm: t("suspendEvent"), run: review(r.id, "suspend_event") })}>{t("suspendEvent")}</Button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </Table>
      )}
      <ListState error={list.error} loading={!list.data && !list.error} truncated={list.data?.truncated} />
    </div>
  );
}

function Settings() {
  const t = useTranslations("admin.settings");
  const errorMessage = useErrorMessage();
  const { data, error, reload } = useList(() => unwrap(api.GET("/api/v1/admin/settings")), "settings");
  const [saveError, setSaveError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  if (!data) return <ListState error={error} loading={!error} />;
  return (
    <Card className="max-w-xl">
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setSaveError(null);
          setSaved(false);
          try {
            const fee = Number(new FormData(e.currentTarget).get("fee"));
            await unwrap(api.PUT("/api/v1/admin/settings", { body: { activation_fee_kzt: fee } }));
            setSaved(true);
            reload();
          } catch (err) {
            setSaveError(err);
          }
        }}
      >
        {saveError ? <Alert kind="error">{errorMessage(saveError)}</Alert> : null}
        <Field key={data.activation_fee_kzt} name="fee" type="number" min={0} step={1} label={t("fee")} hint={t("feeHint")} defaultValue={data.activation_fee_kzt} required />
        <p className="text-sm text-ink-muted">{data.customized ? t("customized") : t("default")}</p>
        <div className="flex items-center gap-3">
          <Button type="submit">{t("save")}</Button>
          {saved && <Toast>{t("saved")}</Toast>}
        </div>
      </form>
    </Card>
  );
}
