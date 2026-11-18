"use client";

import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { Alert, Button, Card, Field, PageTitle } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { useAuth } from "@/lib/auth";
import { useErrorMessage } from "@/lib/use-error-message";

/** Only follow same-site relative paths after sign-in, never an arbitrary URL. */
function safeNext(value: string | null): string | null {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : null;
}

export function LoginForm() {
  const t = useTranslations("auth");
  const tn = useTranslations("nav");
  const errorMessage = useErrorMessage();
  const { login } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const user = await login(String(form.get("email")), String(form.get("password")));
      router.replace(next ?? (user.role === "organizer" ? "/organizer/events" : "/"));
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <Card>
      <PageTitle>{t("login.title")}</PageTitle>
      <form onSubmit={onSubmit} className="space-y-4">
        {next && !error ? <Alert kind="info">{t("required.signIn")}</Alert> : null}
        {error ? <Alert kind="error">{errorMessage(error)}</Alert> : null}
        <Field name="email" type="email" label={t("email")} autoComplete="email" required />
        <Field
          name="password"
          type="password"
          label={t("password")}
          autoComplete="current-password"
          required
        />
        <Button type="submit" disabled={busy} className="w-full">
          {t("login.submit")}
        </Button>
        <div className="flex flex-wrap justify-between gap-x-4 gap-y-2 text-sm">
          <Link href="/forgot-password" className="text-ink-muted underline decoration-1 underline-offset-4 hover:text-ink">
            {t("login.forgot")}
          </Link>
          <span className="text-ink-muted">
            {t("login.noAccount")}{" "}
            <Link href="/register" className="font-semibold text-sky-ink underline decoration-1 underline-offset-4 hover:decoration-2">
              {tn("register")}
            </Link>
          </span>
        </div>
      </form>
    </Card>
  );
}
