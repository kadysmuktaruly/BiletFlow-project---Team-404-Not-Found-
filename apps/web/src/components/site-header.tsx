"use client";

import { useTranslations } from "next-intl";
import { Suspense } from "react";

import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useAuth, type User } from "@/lib/auth";

import { LocaleSwitcher } from "./locale-switcher";
import { NotificationLink } from "./notification-badge";
import { buttonClass } from "./ui";

/** BiletFlow's mark: a ticket with a sun-coloured stub. Decorative; the name follows. */
function Mark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 32 24" className="hidden h-6 w-8 shrink-0 sm:block">
      <path
        d="M4 2h24a2 2 0 0 1 2 2v5a3 3 0 0 0 0 6v5a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-5a3 3 0 0 0 0-6V4a2 2 0 0 1 2-2Z"
        className="fill-ink"
      />
      <path d="M22 2h6a2 2 0 0 1 2 2v5a3 3 0 0 0 0 6v5a2 2 0 0 1-2 2h-6Z" className="fill-sun" />
      <path d="M22 5v14" className="stroke-surface" strokeWidth="1.5" strokeDasharray="2 2" />
    </svg>
  );
}

function navLinkProps(href: string, pathname: string | null) {
  const active = pathname !== null && (pathname === href || pathname.startsWith(`${href}/`));
  return {
    href,
    "aria-current": active ? ("page" as const) : undefined,
    className: `inline-flex min-h-10 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 text-sm font-semibold transition-colors ${
      active ? "bg-ink text-surface" : "text-ink-muted hover:bg-paper hover:text-ink"
    }`,
  };
}

function HeaderLinks({ user, pathname }: { user: User | null; pathname: string | null }) {
  const t = useTranslations("nav");
  const navLink = (href: string) => navLinkProps(href, pathname);
  return (
    <>
      <Link {...navLink("/events")}>{t("events")}</Link>
      {user && (
        <>
          <Link {...navLink("/tickets")}>{t("myTickets")}</Link>
          <Link {...navLink("/orders")}>{t("myOrders")}</Link>
          <Link {...navLink("/support")}>{t("support")}</Link>
          <NotificationLink className={navLink("/notifications").className} />
        </>
      )}
      {user?.role === "platform_admin" && <Link {...navLink("/admin")}>{t("admin")}</Link>}
      {user?.role === "organizer" && (
        <>
          <Link {...navLink("/organizer/events")}>{t("myEvents")}</Link>
          <Link {...navLink("/organizer/analytics")}>{t("analytics")}</Link>
          <Link {...navLink("/organizer/profile")}>{t("profile")}</Link>
        </>
      )}
    </>
  );
}

/** The current path is only known at request time, so this part sits inside <Suspense>. */
function ActiveHeaderLinks({ user }: { user: User | null }) {
  return <HeaderLinks user={user} pathname={usePathname()} />;
}

export function SiteHeader() {
  const t = useTranslations("nav");
  const tc = useTranslations("common");
  const { status, user, logout } = useAuth();
  const router = useRouter();

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur supports-[backdrop-filter]:bg-surface/85">
      <nav
        aria-label={t("main")}
        className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6"
      >
        <Link href="/" className="font-display order-1 inline-flex items-center gap-2 rounded-md text-xl text-ink">
          <Mark />
          {tc("appName")}
        </Link>
        {/* Second row: the links scroll sideways on mobile and wrap on desktop. */}
        <div className="order-3 flex w-full min-w-0 items-center gap-2">
          <div className="relative -ml-4 flex min-w-0 flex-1 items-center gap-1 overflow-x-auto pl-4 lg:ml-0 lg:flex-wrap lg:overflow-visible lg:pl-0">
            <Suspense fallback={<HeaderLinks user={user} pathname={null} />}>
              <ActiveHeaderLinks user={user} />
            </Suspense>
          </div>
          <Suspense>
            <LocaleSwitcher />
          </Suspense>
        </div>
        <div className="order-2 ml-auto flex items-center gap-1 text-sm sm:gap-2">
          {status === "authenticated" && user ? (
            <>
              <span className="hidden max-w-48 truncate text-ink-muted md:inline">{user.full_name}</span>
              <button
                type="button"
                onClick={async () => {
                  await logout();
                  router.push("/");
                }}
                className={buttonClass("ghost", "sm")}
              >
                {t("signOut")}
              </button>
            </>
          ) : status === "anonymous" ? (
            <>
              <Link href="/login" className={`${buttonClass("ghost", "sm")} whitespace-nowrap`}>
                {t("signIn")}
              </Link>
              <Link href="/register" className={`${buttonClass("primary", "sm")} whitespace-nowrap`}>
                {t("register")}
              </Link>
            </>
          ) : null}
        </div>
      </nav>
    </header>
  );
}
