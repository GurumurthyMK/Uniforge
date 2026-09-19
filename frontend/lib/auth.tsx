"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchMe, login as apiLogin, logout as apiLogout, register as apiRegister, type Me, type RegisterInput } from "@/lib/api";

const TOKEN_KEY = "uf_token";

/** Readable session cookie so middleware can gate /app routes (UX only).
 *  Real authorization is enforced server-side by the API per request. */
function setTokenCookie(token: string | null) {
  if (typeof document === "undefined") return;
  if (token) {
    const maxAge = 7 * 24 * 3600;
    document.cookie = `${TOKEN_KEY}=${token}; path=/; max-age=${maxAge}; samesite=lax`;
  } else {
    document.cookie = `${TOKEN_KEY}=; path=/; max-age=0`;
  }
}

function readToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

type AuthState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; me: Me; token: string };

type AuthContextValue = AuthState & {
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (input: RegisterInput) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const router = useRouter();

  const refresh = useCallback(async () => {
    const token = readToken();
    if (!token) {
      setState({ status: "anonymous" });
      return;
    }
    try {
      const me = await fetchMe(token);
      setState({ status: "authenticated", me, token });
    } catch {
      window.localStorage.removeItem(TOKEN_KEY);
      setTokenCookie(null);
      setState({ status: "anonymous" });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const storeSession = useCallback((token: string, me: Me) => {
    window.localStorage.setItem(TOKEN_KEY, token);
    setTokenCookie(token);
    setState({ status: "authenticated", me, token });
  }, []);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const res = await apiLogin(email, password);
      storeSession(res.token, res.user);
      router.push("/app");
    },
    [storeSession, router]
  );

  const signUp = useCallback(
    async (input: RegisterInput) => {
      const res = await apiRegister(input);
      storeSession(res.token, res.user);
      router.push("/app");
    },
    [storeSession, router]
  );

  const signOut = useCallback(async () => {
    const token = readToken();
    if (token) {
      try {
        await apiLogout(token);
      } catch {
        // Revocation is best-effort; always clear local state.
      }
    }
    window.localStorage.removeItem(TOKEN_KEY);
    setTokenCookie(null);
    setState({ status: "anonymous" });
    router.push("/");
  }, [router]);

  const value = useMemo<AuthContextValue>(() => {
    if (state.status === "authenticated") {
      return { ...state, signIn, signUp, signOut, refresh };
    }
    return { ...state, signIn, signUp, signOut, refresh } as AuthContextValue;
  }, [state, signIn, signUp, signOut, refresh]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/** Client-side route guard. UX convenience only — the API authorizes everything. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (auth.status === "anonymous") router.replace("/login");
  }, [auth.status, router]);
  if (auth.status === "loading") return <p className="text-sm text-zinc-500">Loading…</p>;
  if (auth.status === "anonymous") return null;
  return <>{children}</>;
}
