"use client";

import { useTranslations } from "next-intl";
import { Suspense } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { useAuth } from "@/lib/auth";

import { LocaleSwitcher } from "./locale-switcher";

export function SiteHeader() {
  const t = useTranslations("nav");
  const tc = useTranslations("common");
  const { status, user, logout } = useAuth();
  const router = useRouter();

  return (
    <header className="border-b border-gray-200 bg-white">
      <nav
        aria-label="Main"
        className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3"
      >
        <Link href="/" className="text-lg font-bold tracking-tight text-gray-900">
          {tc("appName")}
        </Link>
        <div className="flex flex-1 flex-wrap items-center gap-x-4 text-sm">
          {user?.role === "organizer" && (
            <>
              <Link href="/organizer/events" className="text-gray-700 hover:text-gray-900">
                {t("myEvents")}
              </Link>
              <Link href="/organizer/profile" className="text-gray-700 hover:text-gray-900">
                {t("profile")}
              </Link>
            </>
          )}
        </div>
        <div className="flex items-center gap-4 text-sm">
          <Suspense>
            <LocaleSwitcher />
          </Suspense>
          {status === "authenticated" && user ? (
            <>
              <span className="hidden text-gray-600 sm:inline">{user.full_name}</span>
              <button
                type="button"
                onClick={async () => {
                  await logout();
                  router.push("/");
                }}
                className="font-medium text-gray-900 underline-offset-4 hover:underline"
              >
                {t("signOut")}
              </button>
            </>
          ) : status === "anonymous" ? (
            <>
              <Link href="/login" className="font-medium text-gray-900 hover:underline">
                {t("signIn")}
              </Link>
              <Link
                href="/register"
                className="rounded-md bg-gray-900 px-3 py-1.5 font-semibold text-white hover:bg-gray-700"
              >
                {t("register")}
              </Link>
            </>
          ) : null}
        </div>
      </nav>
    </header>
  );
}
