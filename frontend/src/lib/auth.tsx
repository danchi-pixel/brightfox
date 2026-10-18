import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { LoginPage } from "@/features/auth/LoginPage";
import { api, errorMessage, UNAUTHORIZED_EVENT } from "./api";
import { APP_NAME } from "./brand";

export interface Me {
  authenticated: boolean;
  username?: string;
  role?: "admin" | "learner";
  learner_id?: number | null;
  learner_name?: string | null;
  family?: { id: number; name: string } | null;
  language?: "sl" | "en";
}

interface AuthContextValue {
  me: Me;
  /** A parent: sees and manages the whole family. */
  isAdmin: boolean;
  /** For a learner's account: their own learner id. */
  ownLearnerId: number | null;
  language: "sl" | "en";
  setLanguage: (lang: "sl" | "en" | null) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthGate");
  return ctx;
}

/** Shows the login screen until someone is signed in; any 401 from the API brings it back. */
export function AuthGate({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setMe(await api.get<Me>("/api/auth/status"));
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onUnauthorized = () => setMe({ authenticated: false });
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.post("/api/auth/logout");
    } finally {
      qc.clear();
      setMe({ authenticated: false });
    }
  }, [qc]);

  const setLanguage = useCallback(async (lang: "sl" | "en" | null) => {
    setMe(await api.put<Me>("/api/auth/preferences", { language: lang }));
  }, []);

  if (error && !me) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="font-display text-2xl">{APP_NAME}</p>
        <p className="text-muted-foreground">{error}</p>
        <button className="rounded-xl bg-primary px-4 py-2 font-medium text-primary-foreground" onClick={() => void load()}>
          Try again · Poskusi znova
        </button>
      </div>
    );
  }
  if (!me) return <div className="min-h-dvh bg-background" />;
  if (!me.authenticated) {
    return (
      <LoginPage
        onSignedIn={(signedIn) => {
          qc.clear();
          setMe(signedIn);
        }}
      />
    );
  }
  const isAdmin = me.role === "admin";
  return (
    <AuthContext.Provider
      value={{ me, isAdmin, ownLearnerId: isAdmin ? null : (me.learner_id ?? null), language: me.language ?? "sl", setLanguage, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}
