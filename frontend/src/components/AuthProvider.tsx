"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { User } from "firebase/auth";
import { useTranslations } from "next-intl";
import { api, type Schemas } from "@/lib/api/client";
import { isFirebaseConfigured } from "@/lib/auth";
import { getFirebaseAuth } from "@/lib/firebaseClient";
import { toUiError, type UiError } from "@/lib/api/problem";

type Session = {
  user: Pick<User, "uid" | "email"> | null;
  member: Schemas["MeResponse"] | null;
  unverified: boolean;
  pending: boolean;
  booted: boolean;
  error: UiError | null;
};
type AuthContextValue = Session & {
  configured: boolean;
  ready: boolean;
  retry: () => void;
  refresh: () => Promise<void>;
};
const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is required");
  return value;
}

export default function AuthProvider({ children }: { children: ReactNode }) {
  const configured = isFirebaseConfigured();
  const t = useTranslations();
  const [attempt, setAttempt] = useState(0);
  const [session, setSession] = useState<Session>({
    user: null, member: null, unverified: false, pending: configured, booted: !configured, error: null,
  });

  useEffect(() => {
    if (!configured) return;
    let active = true;
    let sequence = 0;
    let unsubscribe: (() => void) | undefined;
    let controller: AbortController | undefined;
    (async () => {
      const auth = await getFirebaseAuth();
      const { onAuthStateChanged } = await import("firebase/auth");
      if (!active) return;
      unsubscribe = onAuthStateChanged(auth, async (user) => {
        const run = ++sequence;
        controller?.abort();
        controller = new AbortController();
        const who = user ? { uid: user.uid, email: user.email } : null;
        setSession({ user: who, member: null, unverified: false, pending: Boolean(user), booted: true, error: null });
        if (!user) return;
        try {
          const { data, error, response } = await api.GET("/v1/me", { signal: controller.signal });
          if (!active || run !== sequence || auth.currentUser?.uid !== user.uid) return;
          if (data) setSession({ user: who, member: data, unverified: false, pending: false, booted: true, error: null });
          else if (error?.code === "EMAIL_NOT_VERIFIED") {
            setSession({ user: who, member: null, unverified: true, pending: false, booted: true, error: null });
          } else {
            setSession({ user: who, member: null, unverified: false, pending: false, booted: true, error: toUiError(t, error, response.status) });
          }
        } catch (error) {
          if (active && run === sequence) {
            setSession({ user: who, member: null, unverified: false, pending: false, booted: true, error: toUiError(t, error) });
          }
        }
      });
    })().catch(() => {
      if (active) setSession({ user: null, member: null, unverified: false, pending: false, booted: true,
        error: { code: "FIREBASE_INIT_FAILED", status: 0, message: t("auth.initFailed"), fieldErrors: [] } });
    });
    return () => { active = false; ++sequence; controller?.abort(); unsubscribe?.(); };
  }, [configured, attempt, t]);

  async function refresh() {
    if (!configured) return;
    const auth = await getFirebaseAuth();
    const user = auth.currentUser;
    if (user) {
      await user.reload();
      await user.getIdToken(true);
    }
    setAttempt((n) => n + 1);
  }

  const ready = session.booted && !session.pending && !session.error;
  return (
    <AuthContext.Provider value={{ ...session, configured, ready, retry: () => setAttempt((n) => n + 1), refresh }}>
      {children}
    </AuthContext.Provider>
  );
}
