export const AUTH_PAGES = ["/login", "/register", "/forgot-password", "/verify-email", "/auth/action"];

export const PASSWORD_MIN = 8;
export const PASSWORD_MAX = 4096;

const BASE = "https://littlelegs.invalid";

export function safeNext(raw: string | null | undefined, fallback = "/"): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return fallback;
  try {
    const u = new URL(raw, BASE);
    if (u.origin !== BASE || AUTH_PAGES.includes(u.pathname)) return fallback;
    return `${u.pathname}${u.search}${u.hash}`;
  } catch {
    return fallback;
  }
}

export function nextFromContinueUrl(continueUrl: string | null | undefined, origin: string, fallback = "/"): string {
  if (!continueUrl) return fallback;
  try {
    const u = new URL(continueUrl);
    if (u.origin !== origin) return fallback;
    const inner = u.searchParams.get("next");
    return AUTH_PAGES.includes(u.pathname) ? safeNext(inner, fallback) : safeNext(`${u.pathname}${u.search}`, fallback);
  } catch {
    return fallback;
  }
}

export function withNext(path: string, next: string): string {
  return next === "/" ? path : `${path}?next=${encodeURIComponent(next)}`;
}

const OPEN_WHILE_UNVERIFIED = [...AUTH_PAGES, "/privacy", "/terms"];

export function unverifiedRedirect(pathname: string): string | null {
  return OPEN_WHILE_UNVERIFIED.includes(pathname) ? null : withNext("/verify-email", safeNext(pathname));
}

const MESSAGES: Record<string, string> = {
  "auth/invalid-credential": "invalidCredentials",
  "auth/invalid-login-credentials": "invalidCredentials",
  "auth/user-not-found": "invalidCredentials",
  "auth/wrong-password": "invalidCredentials",
  "auth/invalid-email": "invalidEmail",
  "auth/missing-email": "invalidEmail",
  "auth/email-already-in-use": "emailInUse",
  "auth/weak-password": "weakPassword",
  "auth/password-does-not-meet-requirements": "weakPassword",
  "auth/user-disabled": "disabled",
  "auth/too-many-requests": "tooMany",
  "auth/network-request-failed": "network",
  "auth/operation-not-allowed": "providerDisabled",
  "auth/admin-restricted-operation": "providerDisabled",
  "auth/popup-closed-by-user": "cancelled",
  "auth/cancelled-popup-request": "cancelled",
  "auth/user-cancelled": "cancelled",
  "auth/popup-blocked": "popupBlocked",
  "auth/account-exists-with-different-credential": "accountExists",
  "auth/requires-recent-login": "recentLogin",
  "auth/user-mismatch": "userMismatch",
  "auth/credential-already-in-use": "alreadyLinked",
  "auth/provider-already-linked": "alreadyLinked",
  "auth/email-already-exists": "emailInUse",
  "auth/expired-action-code": "expiredLink",
  "auth/invalid-action-code": "invalidLink",
};

export function authErrorKey(code: string | undefined): string | null {
  return code && MESSAGES[code] ? `auth.errors.${MESSAGES[code]}` : null;
}

export function shouldUseRedirect(code: string | undefined): boolean {
  return code === "auth/popup-blocked" || code === "auth/operation-not-supported-in-environment";
}

export function firebaseErrorCode(error: unknown): string | undefined {
  return error && typeof error === "object" && "code" in error && typeof error.code === "string" ? error.code : undefined;
}

export function safeErrorCode(error: unknown, stage: string): string {
  const code = firebaseErrorCode(error);
  if (code && /^auth\/[a-z0-9_.-]{1,200}$/i.test(code)) return code;
  const kind = error instanceof TypeError ? "TYPE_ERROR" : error instanceof Error && error.name === "ChunkLoadError" ? "CHUNK_LOAD_ERROR" : "UNKNOWN_ERROR";
  return `${stage}_${kind}`;
}
