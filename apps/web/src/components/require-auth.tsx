"use client";

import { useTranslations } from "next-intl";
import { useEffect } from "react";

import { usePathname, useRouter } from "@/i18n/navigation";
import { useAuth, type User } from "@/lib/auth";

import { Alert } from "./ui";

/** Client-side gate. The API enforces every permission itself; this only routes the user. */
export function RequireAuth({
  role,
  children,
}: {
  role?: User["role"];
  children: React.ReactNode;
}) {
  const t = useTranslations();
  const { status, user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") {
      router.replace({ pathname: "/login", query: { next: pathname } });
    }
  }, [status, router, pathname]);

  if (status !== "authenticated" || !user) {
    return <p className="text-gray-600">{t("common.loading")}</p>;
  }
  if (role && user.role !== role) {
    return <Alert kind="error">{t("auth.required.organizer")}</Alert>;
  }
  return <>{children}</>;
}
