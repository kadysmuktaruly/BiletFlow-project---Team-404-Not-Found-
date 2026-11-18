"use client";

import type { Schemas } from "@biletflow/api-types";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert, Button, Card, DemoBadge, Field, PageTitle, TextArea } from "@/components/ui";
import { api, ApiError, unwrap } from "@/lib/api";
import { useErrorMessage } from "@/lib/use-error-message";

type Profile = Schemas["OrganizerProfileRead"];
type Payout = Schemas["PayoutAccountRead"];

const blankToNull = (v: FormDataEntryValue | null) => (v && String(v).trim() ? String(v) : null);

export function ProfilePage() {
  const t = useTranslations("organizer");
  const tc = useTranslations("common");
  const errorMessage = useErrorMessage();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [payout, setPayout] = useState<Payout | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [profileState, setProfileState] = useState<{ saved?: boolean; error?: unknown }>({});
  const [payoutState, setPayoutState] = useState<{ saved?: boolean; error?: unknown }>({});

  useEffect(() => {
    unwrap(api.GET("/api/v1/organizer/profile")).then(setProfile).catch(setLoadError);
    unwrap(api.GET("/api/v1/organizer/payout-account"))
      .then(setPayout)
      .catch((err: unknown) => {
        if (!(err instanceof ApiError && err.code === "payout_account_not_found")) setLoadError(err);
      });
  }, []);

  async function saveProfile(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setProfileState({});
    try {
      setProfile(
        await unwrap(
          api.PUT("/api/v1/organizer/profile", {
            body: {
              display_name: String(f.get("display_name")),
              contact_email: String(f.get("contact_email")),
              contact_phone: blankToNull(f.get("contact_phone")),
              description: blankToNull(f.get("description")),
              website_url: blankToNull(f.get("website_url")),
            },
          }),
        ),
      );
      setProfileState({ saved: true });
    } catch (error) {
      setProfileState({ error });
    }
  }

  async function savePayout(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setPayoutState({});
    try {
      setPayout(
        await unwrap(
          api.PUT("/api/v1/organizer/payout-account", {
            body: {
              account_holder_name: String(f.get("account_holder_name")),
              bank_name: String(f.get("bank_name")),
              account_last4: String(f.get("account_last4")),
            },
          }),
        ),
      );
      setPayoutState({ saved: true });
    } catch (error) {
      setPayoutState({ error });
    }
  }

  if (loadError) return <Alert kind="error">{errorMessage(loadError)}</Alert>;
  if (!profile) return <p className="text-gray-600">{tc("loading")}</p>;

  return (
    <div className="space-y-8">
      <Card>
        <PageTitle>{t("profile.title")}</PageTitle>
        <p className="-mt-4 mb-6 text-gray-600">{t("profile.lead")}</p>
        <form onSubmit={saveProfile} className="grid gap-4 sm:grid-cols-2">
          <Field
            name="display_name"
            label={t("profile.displayName")}
            defaultValue={profile.display_name}
            required
            maxLength={200}
          />
          <Field
            name="contact_email"
            type="email"
            label={t("profile.contactEmail")}
            defaultValue={profile.contact_email}
            required
          />
          <Field
            name="contact_phone"
            type="tel"
            label={`${t("profile.contactPhone")} (${tc("optional")})`}
            defaultValue={profile.contact_phone ?? ""}
          />
          <Field
            name="website_url"
            type="url"
            label={`${t("profile.website")} (${tc("optional")})`}
            defaultValue={profile.website_url ?? ""}
            placeholder="https://"
          />
          <TextArea
            name="description"
            label={`${t("profile.description")} (${tc("optional")})`}
            defaultValue={profile.description ?? ""}
            className="sm:col-span-2"
          />
          <div className="flex items-center gap-4 sm:col-span-2">
            <Button type="submit">{tc("save")}</Button>
            {profileState.saved && <span className="text-sm text-green-800">{tc("saved")}</span>}
          </div>
          {profileState.error ? (
            <div className="sm:col-span-2">
              <Alert kind="error">{errorMessage(profileState.error)}</Alert>
            </div>
          ) : null}
        </form>
      </Card>

      <Card>
        <div className="mb-4 flex items-center gap-3">
          <h2 className="text-xl font-bold text-gray-900">{t("payout.title")}</h2>
          <DemoBadge label={tc("demo")} />
        </div>
        <Alert kind="demo">{t("payout.demoNotice")}</Alert>
        {payout && (
          <p className="mt-3 text-sm text-gray-700">
            {t("payout.status", { status: t(`payout.statuses.${payout.status}`) })}
          </p>
        )}
        <form onSubmit={savePayout} className="mt-4 grid gap-4 sm:grid-cols-3">
          <Field
            name="account_holder_name"
            label={t("payout.holder")}
            defaultValue={payout?.account_holder_name ?? ""}
            required
          />
          <Field
            name="bank_name"
            label={t("payout.bank")}
            defaultValue={payout?.bank_name ?? ""}
            required
          />
          <Field
            name="account_last4"
            label={t("payout.last4")}
            hint={t("payout.last4Hint")}
            defaultValue={payout?.account_last4 ?? ""}
            inputMode="numeric"
            pattern="\d{4}"
            maxLength={4}
            required
          />
          <div className="flex items-center gap-4 sm:col-span-3">
            <Button type="submit">{tc("save")}</Button>
            {payoutState.saved && <span className="text-sm text-green-800">{tc("saved")}</span>}
          </div>
          {payoutState.error ? (
            <div className="sm:col-span-3">
              <Alert kind="error">{errorMessage(payoutState.error)}</Alert>
            </div>
          ) : null}
        </form>
      </Card>
    </div>
  );
}
