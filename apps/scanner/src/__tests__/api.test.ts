import { ApiError, errorKey, fetchWithTimeout, isNetworkError, REQUEST_TIMEOUT_MS, unwrap } from "@/lib/api";

const response = (status: number) => ({ ok: status < 400, status }) as Response;

describe("unwrap", () => {
  it("returns data on success", async () => {
    await expect(unwrap(Promise.resolve({ data: { a: 1 }, response: response(200) }))).resolves.toEqual({
      a: 1,
    });
  });

  it("throws the API's error code", async () => {
    const call = Promise.resolve({
      error: { error: { code: "invalid_credentials", message: "x", details: null } },
      response: response(401),
    });
    await expect(unwrap(call)).rejects.toEqual(new ApiError("invalid_credentials"));
  });

  it("reports network failures as 'network'", async () => {
    await expect(unwrap(Promise.reject(new TypeError("Network request failed")))).rejects.toEqual(
      new ApiError("network"),
    );
  });
});

describe("errorKey", () => {
  const known = (k: string) => ["errors.invalid_credentials", "errors.generic"].includes(k);

  it("maps known codes and falls back to generic", () => {
    expect(errorKey(new ApiError("invalid_credentials"), known)).toBe("errors.invalid_credentials");
    expect(errorKey(new ApiError("something_new"), known)).toBe("errors.generic");
    expect(errorKey(new Error("boom"), known)).toBe("errors.generic");
  });
});

describe("fetchWithTimeout", () => {
  const realFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = realFetch;
    jest.useRealTimers();
  });

  it("aborts a request that takes too long, and the client reports it as 'network'", async () => {
    jest.useFakeTimers();
    // A connection that never answers, but stops when aborted (like a real fetch).
    globalThis.fetch = jest.fn(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(Object.assign(new Error("Aborted"), { name: "AbortError" })),
          );
        }),
    ) as typeof fetch;
    const call = unwrap(fetchWithTimeout(new Request("http://api.test/x")).then((r) => ({ response: r })));
    const outcome = expect(call).rejects.toEqual(new ApiError("network"));
    jest.advanceTimersByTime(REQUEST_TIMEOUT_MS - 1);
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    jest.advanceTimersByTime(1);
    await outcome;
  });

  it("passes a quick answer through", async () => {
    const answer = { ok: true, status: 200 } as Response;
    globalThis.fetch = jest.fn(async () => answer) as typeof fetch;
    await expect(fetchWithTimeout(new Request("http://api.test/x"))).resolves.toBe(answer);
  });

  it("uses a timeout well inside what door staff will wait", () => {
    expect(REQUEST_TIMEOUT_MS).toBeLessThanOrEqual(10_000);
  });
});

describe("isNetworkError", () => {
  it("is true only when the API was never reached", () => {
    expect(isNetworkError(new ApiError("network"))).toBe(true);
    expect(isNetworkError(new ApiError("generic"))).toBe(false);
    expect(isNetworkError(new Error("network"))).toBe(false);
  });
});
