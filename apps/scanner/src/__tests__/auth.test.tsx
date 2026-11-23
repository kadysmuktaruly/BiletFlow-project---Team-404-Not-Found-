import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { Pressable, Text } from "react-native";

import pkg from "../../package.json";

import { AuthProvider, useAuth } from "@/lib/auth";

// Set by jest for every test file.
declare const __dirname: string;

// Node's fs, typed just enough for this test (the app has no @types/node).
const fs = jest.requireActual<{ readFileSync(path: string, encoding: "utf8"): string }>("fs");

const mockStore = new Map<string, string>();
const mockPost = jest.fn();
const mockSetToken = jest.fn();

jest.mock("expo-secure-store", () => ({
  setItemAsync: jest.fn(async (k: string, v: string) => void mockStore.set(k, v)),
  getItemAsync: jest.fn(async (k: string) => mockStore.get(k) ?? null),
  deleteItemAsync: jest.fn(async (k: string) => void mockStore.delete(k)),
}));
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  api: { POST: (...a: unknown[]) => mockPost(...a) },
  setAccessToken: (t: string | null) => mockSetToken(t),
}));

const SecureStore = jest.requireMock("expo-secure-store");
const KEY = "biletflow.refresh_token";
const user = { id: "u-1", email: "staff@demo.biletflow.kz", full_name: "Madina Ospanova" };
const session = (refresh: string) => ({
  data: { access_token: "access-1", refresh_token: refresh, expires_in: 900, token_type: "bearer", user },
  response: { ok: true, status: 200 } as Response,
});

function Probe() {
  const auth = useAuth();
  return (
    <>
      <Text>{`${auth.status}:${auth.user?.full_name ?? "-"}`}</Text>
      <Pressable accessibilityRole="button" accessibilityLabel="login" onPress={() => void auth.login("staff@demo.biletflow.kz", "Demo-pass-2026")} />
      <Pressable accessibilityRole="button" accessibilityLabel="logout" onPress={() => void auth.logout()} />
    </>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  mockStore.clear();
});

it("keeps the refresh token in SecureStore and the access token in memory only", async () => {
  mockPost.mockResolvedValue(session("refresh-1"));
  await render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
  await screen.findByText("anonymous:-"); // nothing stored yet
  await fireEvent.press(screen.getByRole("button", { name: "login" }));
  expect(await screen.findByText("authenticated:Madina Ospanova")).toBeTruthy();
  expect(mockPost).toHaveBeenCalledWith("/api/v1/auth/login", {
    body: { email: "staff@demo.biletflow.kz", password: "Demo-pass-2026" },
  });
  expect(SecureStore.setItemAsync).toHaveBeenCalledWith(KEY, "refresh-1");
  expect([...mockStore.values()]).toEqual(["refresh-1"]); // the access token isn't persisted
  expect(mockSetToken).toHaveBeenLastCalledWith("access-1");
});

it("restores the session at launch from SecureStore", async () => {
  mockStore.set(KEY, "refresh-old");
  mockPost.mockResolvedValue(session("refresh-new"));
  await render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
  expect(await screen.findByText("authenticated:Madina Ospanova")).toBeTruthy();
  expect(mockPost).toHaveBeenCalledWith("/api/v1/auth/refresh", { body: { refresh_token: "refresh-old" } });
  expect(mockStore.get(KEY)).toBe("refresh-new");
});

it("sign-out deletes the stored token and forgets the access token", async () => {
  mockStore.set(KEY, "refresh-old");
  mockPost.mockResolvedValue(session("refresh-new"));
  await render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
  await screen.findByText("authenticated:Madina Ospanova");
  await fireEvent.press(screen.getByRole("button", { name: "logout" }));
  expect(await screen.findByText("anonymous:-")).toBeTruthy();
  expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith(KEY);
  expect(mockStore.size).toBe(0);
  expect(mockSetToken).toHaveBeenLastCalledWith(null);
});

it("signs out when the stored session is no longer accepted", async () => {
  mockStore.set(KEY, "refresh-revoked");
  mockPost.mockResolvedValue({
    error: { error: { code: "unauthorized", message: "x", details: null } },
    response: { ok: false, status: 401 } as Response,
  });
  await render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
  await waitFor(() => expect(screen.getByText("anonymous:-")).toBeTruthy());
  expect(mockStore.size).toBe(0);
});

it("never depends on AsyncStorage", () => {
  const deps: Record<string, string> = { ...pkg.dependencies, ...pkg.devDependencies };
  expect(Object.keys(deps)).not.toContain("@react-native-async-storage/async-storage");
  expect(deps).toHaveProperty("expo-secure-store");
  const source = fs.readFileSync(`${__dirname}/../lib/auth.tsx`, "utf8");
  expect(source).not.toMatch(/AsyncStorage|localStorage/);
});
