import createMiddleware from "next-intl/middleware";
import { NextResponse, type NextRequest } from "next/server";

import { routing } from "./i18n/routing";

// Next.js 16 calls this file "proxy" (formerly middleware). It adds the locale prefix,
// e.g. / -> /kk, based on the visitor's Accept-Language header.
const intl = createMiddleware(routing);

// When API_PROXY_TARGET is set (the deployed API's origin), /api/v1/* on this site is
// forwarded there. The browser then talks to one origin, so the httpOnly refresh cookie is
// first-party and survives a reload even when the web app and the API are separate hosts.
// Unset (local development, Docker) the browser calls NEXT_PUBLIC_API_BASE_URL directly.
const API_TARGET = process.env.API_PROXY_TARGET;
const API_SECRET = process.env.API_PROXY_SECRET ?? "";

// Vercel replaces X-Forwarded-For on the way to the API, so the visitor's address travels in
// our own header, which the API trusts only alongside the shared secret (app/ratelimit.py).
const CLIENT_IP_HEADER = "x-biletflow-client-ip";
const SECRET_HEADER = "x-biletflow-proxy-secret";

function forwardToApi(request: NextRequest, target: string): NextResponse {
  const headers = new Headers(request.headers);
  const clientIp = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  headers.delete(CLIENT_IP_HEADER);
  headers.delete(SECRET_HEADER);
  if (clientIp && API_SECRET) {
    headers.set(CLIENT_IP_HEADER, clientIp);
    headers.set(SECRET_HEADER, API_SECRET);
  }
  const url = new URL(request.nextUrl.pathname + request.nextUrl.search, target);
  return NextResponse.rewrite(url, { request: { headers } });
}

export default function proxy(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/api/v1/")) {
    return API_TARGET ? forwardToApi(request, API_TARGET) : NextResponse.next();
  }
  return intl(request);
}

export const config = {
  // Everything except API routes, Next internals and files with an extension. Campaign QR
  // links (/c/BFC1.<token>) contain a dot but are pages, so they're matched explicitly.
  // /api/v1/* is matched for the same-origin API proxy above.
  matcher: [
    "/((?!api|_next|_vercel|.*\\..*).*)",
    "/c/:path*",
    "/:locale(kk|ru|en)/c/:path*",
    "/api/v1/:path*",
  ],
};
