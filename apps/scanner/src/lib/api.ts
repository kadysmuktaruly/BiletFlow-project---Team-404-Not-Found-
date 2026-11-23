import type { ApiErrorBody, paths } from "@biletflow/api-types";
import createClient, { type Middleware } from "openapi-fetch";

// On a phone, "localhost" is the phone itself. Set EXPO_PUBLIC_API_BASE_URL to the LAN IP of
// the machine running the API, e.g. http://192.168.1.20:8000.
export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

const middleware: Middleware = {
  onRequest({ request }) {
    // Tells the API to return the refresh token in the body: there is no cookie jar here.
    request.headers.set("X-Client", "scanner");
    if (accessToken) request.headers.set("Authorization", `Bearer ${accessToken}`);
    return request;
  },
};

/** How long the door waits for the API before saying "not checked in" (SRS 7 targets 2 s). */
export const REQUEST_TIMEOUT_MS = 8_000;

/** `fetch` that gives up after `REQUEST_TIMEOUT_MS`. React Native's fetch has no timeout of
 * its own, so a dead connection would otherwise leave "Checking…" on screen indefinitely. */
export function fetchWithTimeout(request: Request): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  return fetch(request, { signal: controller.signal }).finally(() => clearTimeout(timer));
}

export const api = createClient<paths>({ baseUrl: API_BASE_URL, fetch: fetchWithTimeout });
api.use(middleware);

/** A failed call: the API's stable error `code`, or "network" if the API wasn't reached or
 * didn't answer in time. */
export class ApiError extends Error {
  constructor(readonly code: string) {
    super(code);
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response };

export async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  let result: Result<T>;
  try {
    result = await call;
  } catch {
    throw new ApiError("network");
  }
  if (result.response.ok) return result.data as T;
  const body = result.error as Partial<ApiErrorBody> | undefined;
  throw new ApiError(body?.error?.code ?? "generic");
}

/** True when the API was never reached: no connection, DNS failure or a timeout. */
export function isNetworkError(error: unknown): boolean {
  return error instanceof ApiError && error.code === "network";
}

/** i18n key for an error: `errors.<code>` when translated, else `errors.generic`. */
export function errorKey(error: unknown, known: (key: string) => boolean): string {
  const key = `errors.${error instanceof ApiError ? error.code : "generic"}`;
  return known(key) ? key : "errors.generic";
}
