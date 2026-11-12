import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type Conditions = Schemas["Conditions"];
export type Endpoint = Conditions["start"];
export type CandidateResponse = Schemas["CandidateResponse"];
export type Candidate = Schemas["CandidateOut"];
export type PlanResponse = Schemas["PlanResponse"];
export type Problem = Schemas["Problem"];

const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
export const API_BASE_URL = configuredBaseUrl || (process.env.NODE_ENV === "production" ? "" : "http://127.0.0.1:8000");
export const API_CONFIGURED = API_BASE_URL !== "";

export class ApiNotConfiguredError extends Error {
  constructor() {
    super("API_NOT_CONFIGURED");
    this.name = "ApiNotConfiguredError";
  }
}

export class AppCheckUnavailableError extends Error {
  constructor(cause?: unknown) {
    super("APP_CHECK_UNAVAILABLE", { cause });
    this.name = "AppCheckUnavailableError";
  }
}

type TokenProvider = (forceRefresh?: boolean) => Promise<string | null>;
const providers: { idToken: TokenProvider | null; appCheck: TokenProvider | null; identity: (() => string | null) | null } = {
  idToken: null,
  appCheck: null,
  identity: null,
};

export function setTokenProviders(p: Partial<typeof providers>): void {
  Object.assign(providers, p);
}

const APP_CHECK_PATHS = [/^\/v1\/trips\//, /^\/v1\/endpoints\//, /\/recheck$/, /^\/v1\/feedback$/];
const APP_CHECK_POSTS = [/^\/v1\/check-ins$/];
const needsAppCheck = (method: string, path: string) =>
  APP_CHECK_PATHS.some((re) => re.test(path)) || (method === "POST" && APP_CHECK_POSTS.some((re) => re.test(path)));
const retries = new WeakMap<Request, { request: Request; identity: string | null }>();

const authMiddleware: Middleware = {
  async onRequest({ request, schemaPath }) {
    if (!API_CONFIGURED) throw new ApiNotConfiguredError();
    const identityProvider = providers.identity;
    const identity = identityProvider?.() ?? null;
    if (providers.idToken) {
      const token = await providers.idToken();
      if (token) request.headers.set("Authorization", `Bearer ${token}`);
    }
    if (providers.appCheck && needsAppCheck(request.method, schemaPath)) {
      let token: string | null;
      try {
        token = await providers.appCheck();
      } catch (e) {
        throw new AppCheckUnavailableError(e);
      }
      if (!token) throw new AppCheckUnavailableError();
      request.headers.set("X-Firebase-AppCheck", token);
    }
    if (identityProvider && identityProvider() !== identity) throw new Error("AUTH_SESSION_CHANGED");
    if (request.headers.has("Authorization")) {
      retries.set(request, { request: request.clone(), identity });
    }
    return request;
  },
  async onResponse({ request, response }) {
    const saved = retries.get(request);
    retries.delete(request);
    if (response.status !== 401 || !saved || !providers.idToken || !saved.identity) return response;
    let code: unknown;
    try { code = (await response.clone().json()).code; } catch { return response; }
    if (code !== "AUTH_TOKEN_EXPIRED" && code !== "AUTH_TOKEN_INVALID") return response;
    const path = new URL(request.url).pathname;
    const safe = request.method === "GET" || request.method === "HEAD" || request.headers.has("Idempotency-Key") ||
      (request.method === "POST" && (APP_CHECK_PATHS.some((re) => re.test(path)) || path === "/v1/histories/guest-import")) ||
      (request.method === "DELETE" && path === "/v1/me/registration");
    if (!safe || saved.identity !== providers.identity?.() || request.signal.aborted) return response;
    try {
      const token = await providers.idToken(true);
      if (!token || saved.identity !== providers.identity?.() || request.signal.aborted) return response;
      saved.request.headers.set("Authorization", `Bearer ${token}`);
      return await fetch(saved.request);
    } catch {
      return response;
    }
  },
};

export const api = createClient<paths>({ baseUrl: API_BASE_URL });
api.use(authMiddleware);
