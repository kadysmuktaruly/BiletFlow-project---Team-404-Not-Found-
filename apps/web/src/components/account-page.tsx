"use client";

import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";

import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useAuth, type User } from "@/lib/auth";
import { useErrorMessage } from "@/lib/use-error-message";

import { RequireAuth } from "./require-auth";
import { Alert, Button, buttonClass, Card, Field, LINK, modalClass, PageTitle, SECTION_TITLE } from "./ui";

/**
 * The signed-in user's account: who they are, and deleting the account (DELETE /me).
 * Deletion asks for the current password; the API anonymises the account and ends every
 * session.
 */
export function AccountPage() {
  const t = useTranslations("account.delete");
  const [deleted, setDeleted] = useState(false);

  // Rendered outside RequireAuth: once signed out, the gate would send the user to sign in.
  if (deleted) {
    return (
      <Card className="space-y-4">
        <Alert kind="success">{t("done")}</Alert>
        <Link href="/" className={buttonClass("secondary")}>
          {t("home")}
        </Link>
      </Card>
    );
  }
  return (
    <RequireAuth>
      <AccountDetails onDeleted={() => setDeleted(true)} />
    </RequireAuth>
  );
}

function AccountDetails({ onDeleted }: { onDeleted: () => void }) {
  const t = useTranslations("account");
  const { user } = useAuth();
  if (!user) return null;

  return (
    <div className="space-y-8">
      <Card>
        <PageTitle>{t("title")}</PageTitle>
        <dl className="grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm font-semibold text-ink-muted">{t("name")}</dt>
            <dd className="break-words text-ink">{user.full_name}</dd>
          </div>
          <div>
            <dt className="text-sm font-semibold text-ink-muted">{t("email")}</dt>
            <dd className="break-words text-ink">{user.email}</dd>
          </div>
        </dl>
        {user.role === "organizer" && (
          <p className="mt-6">
            <Link href="/organizer/profile" className={LINK}>
              {t("organizerProfile")}
            </Link>
          </p>
        )}
      </Card>
      <DeleteAccount user={user} onDeleted={onDeleted} />
    </div>
  );
}

function DeleteAccount({ user, onDeleted }: { user: User; onDeleted: () => void }) {
  const t = useTranslations("account.delete");
  const errorMessage = useErrorMessage();
  const { logout } = useAuth();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const startRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);

  // Return focus to the button that opened the form when it closes.
  useEffect(() => {
    if (wasOpen.current && !open) startRef.current?.focus();
    wasOpen.current = open;
  }, [open]);

  function close() {
    setOpen(false);
    setError(null);
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const password = String(new FormData(e.currentTarget).get("password") ?? "");
    setBusy(true);
    setError(null);
    try {
      await unwrap(api.DELETE("/api/v1/me", { body: { password } }));
      onDeleted();
      await logout();
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <Card className="space-y-4">
      <h2 className={`${SECTION_TITLE} text-danger`}>{t("title")}</h2>
      <p className="text-ink">{t("lead")}</p>
      <p className="text-sm text-ink-muted">{t("keeps")}</p>
      {user.role === "platform_admin" ? (
        <Alert kind="info">{t("adminBlocked")}</Alert>
      ) : (
        <>
          {user.role === "organizer" && <Alert kind="info">{t("organizer")}</Alert>}
          {open ? (
            <form
              role="alertdialog"
              aria-labelledby={`${id}-title`}
              aria-describedby={`${id}-text`}
              className={modalClass(true)}
              onKeyDown={(e) => {
                if (e.key === "Escape") close();
              }}
              onSubmit={onSubmit}
            >
              <h3 id={`${id}-title`} className="text-lg font-bold text-danger">
                {t("confirmTitle")}
              </h3>
              <p id={`${id}-text`} className="text-sm text-ink">
                {t("confirmText")}
              </p>
              {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
              <Field
                name="password"
                type="password"
                label={t("password")}
                autoComplete="current-password"
                required
                maxLength={128}
                autoFocus
              />
              <div className="flex flex-wrap gap-2">
                <Button type="submit" variant="danger" disabled={busy}>
                  {busy ? t("deleting") : t("confirm")}
                </Button>
                <Button type="button" variant="secondary" onClick={close} disabled={busy}>
                  {t("cancel")}
                </Button>
              </div>
            </form>
          ) : (
            <Button ref={startRef} type="button" variant="danger" onClick={() => setOpen(true)}>
              {t("start")}
            </Button>
          )}
        </>
      )}
    </Card>
  );
}
