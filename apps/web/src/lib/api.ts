import type { ApiErrorBody, paths } from "@biletflow/api-types";
import createClient, { type Middleware } from "openapi-fetch";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// The access token lives in memory only. The long-lived refresh token is an httpOnly cookie
// the browser sends to /api/v1/auth automatically, so page scripts never see it.
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

const withAccessToken: Middleware = {
  onRequest({ request }) {
    if (accessToken) request.headers.set("Authorization", `Bearer ${accessToken}`);
    return request;
  },
};

/** Typed client for the BiletFlow API. Paths and bodies come from packages/api-types. */
export const api = createClient<paths>({ baseUrl: API_BASE_URL, credentials: "include" });
api.use(withAccessToken);

/** A failed call: the API's stable error `code`, or "network" if the API wasn't reached. */
export class ApiError extends Error {
  constructor(
    readonly code: string,
    readonly fields: Record<string, string> = {},
  ) {
    super(code);
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/**
 * Unwrap an openapi-fetch result: return the data, or throw an ApiError carrying the error
 * code from the standard `{"error": {...}}` body. Validation errors also carry per-field
 * codes keyed by the last element of `loc`, so forms can mark the right input.
 */
export async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  let result: Result<T>;
  try {
    result = await call;
  } catch {
    throw new ApiError("network");
  }
  if (result.response.ok) return result.data as T;
  const body = result.error as Partial<ApiErrorBody> | undefined;
  const fields: Record<string, string> = {};
  for (const detail of body?.error?.details ?? []) {
    const key = detail.loc[detail.loc.length - 1];
    if (typeof key === "string") fields[key] = detail.type;
  }
  throw new ApiError(body?.error?.code ?? "generic", fields);
}
