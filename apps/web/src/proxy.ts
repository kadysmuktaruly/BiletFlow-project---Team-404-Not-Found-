import createMiddleware from "next-intl/middleware";

import { routing } from "./i18n/routing";

// Next.js 16 calls this file "proxy" (formerly middleware). It adds the locale prefix,
// e.g. / -> /kk, based on the visitor's Accept-Language header.
export default createMiddleware(routing);

export const config = {
  // Everything except API routes, Next internals and files with an extension. Campaign QR
  // links (/c/BFC1.<token>) contain a dot but are pages, so they're matched explicitly.
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)", "/c/:path*", "/:locale(kk|ru|en)/c/:path*"],
};
