"use client";

import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";

import { usePathname, useRouter } from "@/i18n/navigation";
import { routing, type Locale } from "@/i18n/routing";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function LocaleSwitcher() {
  const t = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user, setUser } = useAuth();

  async function change(next: Locale) {
    const query = Object.fromEntries(searchParams.entries());
    router.replace({ pathname, query }, { locale: next });
    // Signed-in users get their emails in the language they browse in.
    if (user && user.locale !== next) {
      const { data } = await api.PATCH("/api/v1/me", { body: { locale: next } });
      if (data) setUser(data);
    }
  }

  return (
    <label className="flex items-center gap-2 text-sm text-gray-700">
      <span className="sr-only">{t("language")}</span>
      <select
        value={locale}
        onChange={(e) => void change(e.target.value as Locale)}
        className="rounded-md border border-gray-300 bg-white px-2 py-1 text-sm"
      >
        {routing.locales.map((l) => (
          <option key={l} value={l} lang={l}>
            {t(`locales.${l}`)}
          </option>
        ))}
      </select>
    </label>
  );
}
