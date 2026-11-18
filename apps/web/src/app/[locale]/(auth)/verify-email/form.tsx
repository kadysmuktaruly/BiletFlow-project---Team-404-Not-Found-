"use client";

import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Alert, Button, Card, Field, PageTitle } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

export function VerifyEmailForm() {
  const t = useTranslations("auth");
  const tn = useTranslations("nav");
  const errorMessage = useErrorMessage();
  const token = useSearchParams().get("token");
  const [state, setState] = useState<"working" | "done" | "failed">(token ? "working" : "failed");
  const [error, setError] = useState<unknown>(null);
  const [resent, setResent] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true; // React strict mode runs effects twice in development
    unwrap(api.POST("/api/v1/auth/verify-email", { body: { token } }))
      .then(() => setState("done"))
      .catch((err: unknown) => {
        setError(err);
        setState("failed");
      });
  }, [token]);

  async function resend(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get("email"));
    await api.POST("/api/v1/auth/resend-verification", { body: { email } });
    setResent(true);
  }

  return (
    <Card>
      <PageTitle>{t("verify.title")}</PageTitle>
      {state === "working" && <p className="text-gray-700">{t("verify.working")}</p>}
      {state === "done" && (
        <div className="space-y-4">
          <Alert kind="success">{t("verify.success")}</Alert>
          <Link href="/login" className="font-medium text-gray-900 underline">
            {tn("signIn")}
          </Link>
        </div>
      )}
      {state === "failed" && (
        <div className="space-y-6">
          <Alert kind="error">{token ? errorMessage(error) : t("verify.missingToken")}</Alert>
          <form onSubmit={resend} className="space-y-3">
            <h2 className="font-semibold text-gray-900">{t("verify.resendTitle")}</h2>
            {resent ? (
              <Alert kind="success">{t("verify.resent")}</Alert>
            ) : (
              <>
                <Field name="email" type="email" label={t("email")} required />
                <Button type="submit" variant="secondary">
                  {t("verify.resend")}
                </Button>
              </>
            )}
          </form>
        </div>
      )}
    </Card>
  );
}
