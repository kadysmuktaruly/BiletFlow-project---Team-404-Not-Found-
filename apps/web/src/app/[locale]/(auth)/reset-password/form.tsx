"use client";

import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { Alert, Button, Card, Field, PageTitle } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

export function ResetPasswordForm() {
  const t = useTranslations("auth");
  const tn = useTranslations("nav");
  const errorMessage = useErrorMessage();
  const token = useSearchParams().get("token");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!token) return;
    const new_password = String(new FormData(e.currentTarget).get("new_password"));
    setBusy(true);
    setError(null);
    try {
      await unwrap(api.POST("/api/v1/auth/reset-password", { body: { token, new_password } }));
      setDone(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <PageTitle>{t("reset.title")}</PageTitle>
      {done ? (
        <div className="space-y-4">
          <Alert kind="success">{t("reset.success")}</Alert>
          <Link href="/login" className="font-medium text-gray-900 underline">
            {tn("signIn")}
          </Link>
        </div>
      ) : !token ? (
        <Alert kind="error">{t("verify.missingToken")}</Alert>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
          <Field
            name="new_password"
            type="password"
            label={t("reset.newPassword")}
            hint={t("passwordHint")}
            autoComplete="new-password"
            required
            minLength={8}
          />
          <Button type="submit" disabled={busy} className="w-full">
            {t("reset.submit")}
          </Button>
        </form>
      )}
    </Card>
  );
}
