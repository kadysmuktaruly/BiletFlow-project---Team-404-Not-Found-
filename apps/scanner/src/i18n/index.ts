import { getLocales } from "expo-localization";
import { createInstance } from "i18next";
import { initReactI18next } from "react-i18next";

import en from "@/locales/en.json";
import kk from "@/locales/kk.json";
import ru from "@/locales/ru.json";

export const SUPPORTED_LOCALES = ["kk", "ru", "en"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

/** The first device language BiletFlow supports, else Kazakh (SRS 7: kk and ru first). */
export function pickLocale(deviceLanguages: (string | null | undefined)[]): Locale {
  for (const lang of deviceLanguages) {
    const match = SUPPORTED_LOCALES.find((l) => l === lang?.toLowerCase());
    if (match) return match;
  }
  return "kk";
}

const i18n = createInstance();

void i18n.use(initReactI18next).init({
  resources: { kk: { translation: kk }, ru: { translation: ru }, en: { translation: en } },
  lng: pickLocale(getLocales().map((l) => l.languageCode)),
  fallbackLng: "kk",
  interpolation: { escapeValue: false }, // React already escapes
});

export default i18n;
