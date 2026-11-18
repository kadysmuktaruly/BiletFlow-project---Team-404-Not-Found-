"use client";

import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Alert, Button, Card, Field, PageTitle } from "@/components/ui";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { api, ApiError, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

export function RegisterForm() {
  const t = useTranslations("auth");
  const locale = useLocale() as Locale;
  const errorMessage = useErrorMessage();
  const router = useRouter();
  const pathname = usePathname();
  // The "check your inbox" state is kept in the URL, so following any link to /register
  // (the header's "Create account") drops the flag and shows a fresh form.
  const sent = useSearchParams().get("sent") === "1";
  const [role, setRole] = useState<"attendee" | "organizer">("attendee");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [mismatch, setMismatch] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const email = String(form.get("email"));
    const password = String(form.get("password"));
    if (password !== String(form.get("password_confirm"))) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    setBusy(true);
    setError(null);
    try {
      await unwrap(
        api.POST("/api/v1/auth/register", {
          body: {
            email,
            password,
            full_name: String(form.get("full_name")),
            role,
            locale,
          },
        }),
      );
      setSentTo(email);
      router.replace(`${pathname}?sent=1`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (sent && sentTo) {
    return (
      <Card>
        <PageTitle>{t("register.doneTitle")}</PageTitle>
        <Alert kind="success">{t("register.done", { email: sentTo })}</Alert>
      </Card>
    );
  }

  const fields = error instanceof ApiError ? error.fields : {};
  return (
    <Card>
      <PageTitle>{t("register.title")}</PageTitle>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
        <Field
          name="full_name"
          label={t("fullName")}
          autoComplete="name"
          required
          maxLength={200}
          error={fields.full_name && errorMessage(error)}
        />
        <Field
          name="email"
          type="email"
          label={t("email")}
          autoComplete="email"
          required
          error={fields.email && errorMessage(error)}
        />
        <Field
          name="password"
          type={showPassword ? "text" : "password"}
          label={t("password")}
          hint={t("passwordHint")}
          autoComplete="new-password"
          required
          minLength={8}
          error={fields.password && t("passwordHint")}
        />
        <Field
          name="password_confirm"
          type={showPassword ? "text" : "password"}
          label={t("confirmPassword")}
          autoComplete="new-password"
          required
          minLength={8}
          error={mismatch ? t("passwordMismatch") : undefined}
        />
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={showPassword}
            onChange={(e) => setShowPassword(e.target.checked)}
            className="h-4 w-4"
          />
          {t("showPassword")}
        </label>
        <fieldset>
          <legend className="mb-1 text-sm font-medium text-ink">{t("register.role")}</legend>
          <div className="grid grid-cols-2 gap-2">
            {(["attendee", "organizer"] as const).map((r) => (
              <label
                key={r}
                className={`flex min-h-11 cursor-pointer items-center rounded-full border px-4 text-sm font-semibold has-[:focus-visible]:outline has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-sky-ink ${role === r ? "border-ink bg-ink text-surface" : "border-line-strong bg-surface text-ink"}`}
              >
                <input
                  type="radio"
                  name="role"
                  value={r}
                  checked={role === r}
                  onChange={() => setRole(r)}
                  className="sr-only"
                />
                {r === "attendee" ? t("register.roleAttendee") : t("register.roleOrganizer")}
              </label>
            ))}
          </div>
        </fieldset>
        <Button type="submit" disabled={busy} className="w-full">
          {t("register.submit")}
        </Button>
        <p className="text-center text-sm text-ink-muted">
          {t("register.haveAccount")}{" "}
          <Link href="/login" className="font-semibold text-sky-ink underline decoration-1 underline-offset-4 hover:decoration-2">
            {t("login.submit")}
          </Link>
        </p>
      </form>
    </Card>
  );
}
