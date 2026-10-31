import { defineRouting } from "next-intl/routing";

// SRS 7: Kazakh and Russian first, English as an additional locale.
export const routing = defineRouting({
  locales: ["kk", "ru", "en"],
  defaultLocale: "kk",
  localePrefix: "always",
});

export type Locale = (typeof routing.locales)[number];
