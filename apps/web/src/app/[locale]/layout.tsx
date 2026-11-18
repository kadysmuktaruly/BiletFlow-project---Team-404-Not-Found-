import type { Metadata } from "next";
import { Geologica } from "next/font/google";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { routing } from "@/i18n/routing";
import { AuthProvider } from "@/lib/auth";

import "../globals.css";

// One variable family for the whole app (docs/design-direction.md). The sharpness axis
// (SHRP) gives headlines their cut corners; cyrillic-ext carries the Kazakh letters.
const geologica = Geologica({
  subsets: ["latin", "cyrillic", "cyrillic-ext"],
  axes: ["SHRP"],
  variable: "--font-geologica",
  display: "swap",
});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: LayoutProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "common" });
  return { title: { default: t("appName"), template: `%s · ${t("appName")}` }, description: t("tagline") };
}

export default async function LocaleLayout({ children, params }: LayoutProps<"/[locale]">) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  return (
    <html lang={locale} className={`${geologica.variable} h-full`}>
      <body className="flex min-h-full flex-col font-sans">
        <NextIntlClientProvider>
          <AuthProvider>
            <SiteHeader />
            <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-10">{children}</main>
            <SiteFooter />
          </AuthProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
