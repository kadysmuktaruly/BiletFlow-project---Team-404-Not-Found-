"use client";

import type { Schemas } from "@biletflow/api-types";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, setAccessToken, unwrap } from "./api";

export type User = Schemas["UserRead"];
type Session = Schemas["TokenResponse"];

type AuthState = {
  status: "loading" | "authenticated" | "anonymous";
  user: User | null;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (user: User) => void;
};

const AuthContext = createContext<AuthState | null>(null);

const REFRESH_MARGIN_SECONDS = 60;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>("loading");
  const [expiresIn, setExpiresIn] = useState<number | null>(null);

  const start = useCallback((session: Session) => {
    setAccessToken(session.access_token);
    setUser(session.user);
    setExpiresIn(session.expires_in);
    setStatus("authenticated");
  }, []);

  const end = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setExpiresIn(null);
    setStatus("anonymous");
  }, []);

  // Restores the session from the refresh cookie (on first load), and renews it before the
  // 15-minute access token expires (while the tab stays open).
  useEffect(() => {
    const delay =
      expiresIn === null ? 0 : Math.max(expiresIn - REFRESH_MARGIN_SECONDS, 30) * 1000;
    const timer = setTimeout(() => {
      unwrap(api.POST("/api/v1/auth/refresh", {})).then(start, end);
    }, delay);
    return () => clearTimeout(timer);
  }, [expiresIn, start, end]);

  const login = useCallback(
    async (email: string, password: string) => {
      const session = await unwrap(
        api.POST("/api/v1/auth/login", { body: { email, password } }),
      );
      start(session);
      return session.user;
    },
    [start],
  );

  const logout = useCallback(async () => {
    try {
      await api.POST("/api/v1/auth/logout");
    } finally {
      end();
    }
  }, [end]);

  const value = useMemo(
    () => ({ status, user, login, logout, setUser }),
    [status, user, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
