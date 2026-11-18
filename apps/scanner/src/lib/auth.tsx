import type { Schemas } from "@biletflow/api-types";
import * as SecureStore from "expo-secure-store";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, setAccessToken, unwrap } from "./api";

export type User = Schemas["UserRead"];
type Session = Schemas["TokenResponse"];

// The refresh token is kept in the OS keychain / keystore, never in plain storage.
const REFRESH_KEY = "biletflow.refresh_token";

type AuthState = {
  status: "loading" | "authenticated" | "anonymous";
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>("loading");
  const [expiresIn, setExpiresIn] = useState<number | null>(null);

  const start = useCallback(async (session: Session) => {
    setAccessToken(session.access_token);
    if (session.refresh_token) await SecureStore.setItemAsync(REFRESH_KEY, session.refresh_token);
    setUser(session.user);
    setExpiresIn(session.expires_in);
    setStatus("authenticated");
  }, []);

  const end = useCallback(async () => {
    setAccessToken(null);
    await SecureStore.deleteItemAsync(REFRESH_KEY);
    setUser(null);
    setExpiresIn(null);
    setStatus("anonymous");
  }, []);

  // Restore the session at launch, then renew the access token a minute before it expires.
  useEffect(() => {
    const delay = expiresIn === null ? 0 : Math.max(expiresIn - 60, 30) * 1000;
    const timer = setTimeout(async () => {
      const refresh_token = await SecureStore.getItemAsync(REFRESH_KEY);
      if (!refresh_token) return void end();
      unwrap(api.POST("/api/v1/auth/refresh", { body: { refresh_token } })).then(start, end);
    }, delay);
    return () => clearTimeout(timer);
  }, [expiresIn, start, end]);

  const login = useCallback(
    async (email: string, password: string) => {
      await start(await unwrap(api.POST("/api/v1/auth/login", { body: { email, password } })));
    },
    [start],
  );

  const value = useMemo(() => ({ status, user, login, logout: end }), [status, user, login, end]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
