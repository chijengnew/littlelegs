import { ApiNotConfiguredError, AppCheckUnavailableError, type Problem } from "./client";

export type UiError = {
  code: string;
  status: number;
  message: string;
  fieldErrors: { loc: string; msg: string }[];
  limitWindow?: string | null;
};

type T = (key: string, values?: Record<string, string | number>) => string;

const CODE_MESSAGES: Record<string, string> = {
  DEPARTURE_PASSED: "errors.departurePassed",
  VALIDATION_FAILED: "errors.validationFailed",
  OUT_OF_SERVICE_AREA: "errors.outOfArea",
  ENDPOINT_NOT_FOUND: "errors.endpointNotFound",
  REAUTH_REQUIRED: "errors.reauthRecent",
  EMAIL_NOT_VERIFIED: "accountMenu.unverifiedHint",
};

function appCheckMessage(t: T): string {
  return process.env.NODE_ENV === "development" ? t("errors.appCheckDev") : t("errors.appCheck");
}

export function toUiError(t: T, err: unknown, status?: number): UiError {
  if (typeof err === "object" && err !== null && "code" in err && typeof err.code === "string" && err.code.startsWith("auth/")) {
    return { code: "AUTH_REAUTH_REQUIRED", status: 401, message: t("auth.reauthRequired"), fieldErrors: [] };
  }
  if (err instanceof ApiNotConfiguredError) {
    return { code: "API_NOT_CONFIGURED", status: 0, message: t("errors.notConnected"), fieldErrors: [] };
  }
  if (err instanceof AppCheckUnavailableError) {
    return { code: "APP_CHECK_UNAVAILABLE", status: 0, message: appCheckMessage(t), fieldErrors: [] };
  }
  if (err instanceof TypeError || err === undefined) {
    return { code: "NETWORK", status: 0, message: t("errors.network"), fieldErrors: [] };
  }
  const p = err as Partial<Problem>;
  const code = p.code ?? "UNKNOWN";
  const httpStatus = p.status ?? status ?? 0;
  let message = p.detail ?? p.title ?? t("errors.generic");
  if (code in CODE_MESSAGES) message = t(CODE_MESSAGES[code]);
  else if (["AUTH_TOKEN_EXPIRED", "AUTH_TOKEN_INVALID", "AUTH_REAUTH_REQUIRED"].includes(code)) message = t("auth.reauthRequired");
  else if (code === "APP_CHECK_FAILED" || code === "APP_CHECK_REQUIRED") message = appCheckMessage(t);
  else if (httpStatus === 429 && code !== "MONTHLY_QUOTA_EXHAUSTED" && !p.detail) message = t("errors.rateLimited");
  const fieldMessage = code === "VALIDATION_FAILED" ? t("errors.fieldCheck") : null;
  const fieldErrors = (p.errors ?? []).map((e) => ({
    loc: (e.loc ?? []).filter((x) => x !== "body").join("."),
    msg: fieldMessage ?? e.msg ?? "",
  }));
  return { code, status: httpStatus, message, fieldErrors, limitWindow: p.limit_window };
}
