import { ApiError, errorKey, unwrap } from "@/lib/api";

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
