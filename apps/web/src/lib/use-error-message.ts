"use client";

import { useTranslations } from "next-intl";

import { ApiError } from "./api";

/** Turn any thrown value into a translated message. API error codes map to `errors.<code>`. */
export function useErrorMessage(): (error: unknown) => string {
  const t = useTranslations("errors");
  return (error) => {
    const code = error instanceof ApiError ? error.code : "generic";
    return t.has(code) ? t(code) : t("generic");
  };
}
