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

export const api = createClient<paths>({ baseUrl: API_BASE_URL });
api.use(middleware);

/** A failed call: the API's stable error `code`, or "network" if the API wasn't reached. */
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

/** i18n key for an error: `errors.<code>` when translated, else `errors.generic`. */
export function errorKey(error: unknown, known: (key: string) => boolean): string {
  const key = `errors.${error instanceof ApiError ? error.code : "generic"}`;
  return known(key) ? key : "errors.generic";
}
