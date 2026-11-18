"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Alert, Button, Card, Field, PageTitle } from "@/components/ui";
import { api, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

export function ForgotPasswordForm() {
  const t = useTranslations("auth");
  const errorMessage = useErrorMessage();
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get("email"));
    setBusy(true);
    setError(null);
    try {
      await unwrap(api.POST("/api/v1/auth/forgot-password", { body: { email } }));
      setSentTo(email);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <PageTitle>{t("forgot.title")}</PageTitle>
      {sentTo ? (
        <Alert kind="success">{t("forgot.done", { email: sentTo })}</Alert>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          <p className="text-gray-700">{t("forgot.lead")}</p>
          {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
          <Field name="email" type="email" label={t("email")} autoComplete="email" required />
          <Button type="submit" disabled={busy} className="w-full">
            {t("forgot.submit")}
          </Button>
        </form>
      )}
    </Card>
  );
}
