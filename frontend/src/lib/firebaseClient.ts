import type { Auth } from "firebase/auth";
import { isFirebaseConfigured } from "./auth";
import { setTokenProviders } from "./api/client";

let initialization: Promise<Auth> | undefined;
let currentAuth: Auth | undefined;

export function currentFirebaseUid(): string | null {
  return currentAuth?.currentUser?.uid ?? null;
}

export function getFirebaseAuth(): Promise<Auth> {
  if (typeof window === "undefined" || !isFirebaseConfigured()) {
    return Promise.reject(new Error("FIREBASE_NOT_CONFIGURED"));
  }
  if (!initialization) {
    initialization = (async () => {
      const [{ getApps, getApp, initializeApp }, { getAuth }] = await Promise.all([
        import("firebase/app"),
        import("firebase/auth"),
      ]);
      const app = getApps().some((a) => a.name === "[DEFAULT]") ? getApp() : initializeApp({
        apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
        authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
        projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
        appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
      });
      const siteKey = process.env.NEXT_PUBLIC_RECAPTCHA_ENTERPRISE_SITE_KEY;
      if (siteKey) {
        const { initializeAppCheck, ReCaptchaEnterpriseProvider, getToken } = await import("firebase/app-check");
        const local = ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);
        if (process.env.NODE_ENV === "development" && local && process.env.NEXT_PUBLIC_APP_CHECK_DEBUG === "true") {
          (self as typeof self & { FIREBASE_APPCHECK_DEBUG_TOKEN?: boolean }).FIREBASE_APPCHECK_DEBUG_TOKEN = true;
        }
        const appCheck = initializeAppCheck(app, {
          provider: new ReCaptchaEnterpriseProvider(siteKey),
          isTokenAutoRefreshEnabled: true,
        });
        setTokenProviders({ appCheck: async () => (await getToken(appCheck)).token });
      }
      const auth = getAuth(app);
      auth.languageCode = "zh-TW";
      currentAuth = auth;
      setTokenProviders({
        identity: () => auth.currentUser?.uid ?? null,
        idToken: async (forceRefresh = false) => {
          await auth.authStateReady();
          const user = auth.currentUser;
          if (!user) return null;
          const token = await user.getIdToken(forceRefresh);
          if (auth.currentUser?.uid !== user.uid) throw new Error("AUTH_SESSION_CHANGED");
          return token;
        },
      });
      return auth;
    })().catch((error) => {
      initialization = undefined;
      throw error;
    });
  }
  return initialization;
}
