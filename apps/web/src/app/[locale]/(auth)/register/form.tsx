"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Alert, Button, Card, Field, PageTitle } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { api, ApiError, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

export function RegisterForm() {
  const t = useTranslations("auth");
  const locale = useLocale() as Locale;
  const errorMessage = useErrorMessage();
  const [role, setRole] = useState<"attendee" | "organizer">("attendee");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const email = String(form.get("email"));
    setBusy(true);
    setError(null);
    try {
      await unwrap(
        api.POST("/api/v1/auth/register", {
          body: {
            email,
            password: String(form.get("password")),
            full_name: String(form.get("full_name")),
            role,
            locale,
          },
        }),
      );
      setSentTo(email);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (sentTo) {
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
          type="password"
          label={t("password")}
          hint={t("passwordHint")}
          autoComplete="new-password"
          required
          minLength={8}
          error={fields.password && t("passwordHint")}
        />
        <fieldset>
          <legend className="mb-1 text-sm font-medium text-gray-900">{t("register.role")}</legend>
          <div className="grid grid-cols-2 gap-2">
            {(["attendee", "organizer"] as const).map((r) => (
              <label
                key={r}
                className={`cursor-pointer rounded-md border px-3 py-2 text-sm ${role === r ? "border-gray-900 bg-gray-900 text-white" : "border-gray-300 bg-white text-gray-900"}`}
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
        <p className="text-center text-sm text-gray-600">
          {t("register.haveAccount")}{" "}
          <Link href="/login" className="font-medium text-gray-900 underline">
            {t("login.submit")}
          </Link>
        </p>
      </form>
    </Card>
  );
}
