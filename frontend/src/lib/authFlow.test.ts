import { describe, expect, test } from "vitest";
import {
  authErrorKey, nextFromContinueUrl, safeErrorCode, safeNext, shouldUseRedirect, unverifiedRedirect, withNext,
} from "./authFlow";

describe("safeNext", () => {
  test("站內路徑保留查詢字串", () => {
    expect(safeNext("/account?tab=history")).toBe("/account?tab=history");
    expect(safeNext("/places/abc")).toBe("/places/abc");
  });

  test("外站、協定相對與反斜線網址一律回首頁", () => {
    for (const bad of ["https://evil.example/", "//evil.example", "/\\evil.example", "javascript:alert(1)", "account", ""]) {
      expect(safeNext(bad)).toBe("/");
    }
    expect(safeNext(null, "/account")).toBe("/account");
  });

  test("不返回登入相關頁，避免循環", () => {
    expect(safeNext("/login?next=/account")).toBe("/");
    expect(safeNext("/verify-email")).toBe("/");
  });
});

describe("nextFromContinueUrl", () => {
  const origin = "http://localhost:3000";
  test("取出同源 continueUrl 內的最終返回位置", () => {
    expect(nextFromContinueUrl(`${origin}/verify-email?next=%2Faccount`, origin)).toBe("/account");
    expect(nextFromContinueUrl(`${origin}/places/abc`, origin)).toBe("/places/abc");
  });

  test("外站或格式錯誤回 fallback", () => {
    expect(nextFromContinueUrl("https://evil.example/account", origin)).toBe("/");
    expect(nextFromContinueUrl(`${origin}/login?next=https://evil.example`, origin)).toBe("/");
    expect(nextFromContinueUrl("not a url", origin)).toBe("/");
    expect(nextFromContinueUrl(null, origin, "/account")).toBe("/account");
  });
});

test("withNext 只在非首頁時帶參數", () => {
  expect(withNext("/login", "/")).toBe("/login");
  expect(withNext("/login", "/account?tab=a")).toBe("/login?next=%2Faccount%3Ftab%3Da");
});

describe("unverifiedRedirect（註冊未完成只能停在驗證相關頁）", () => {
  test("其他頁面轉到驗證頁，並記住原頁面", () => {
    expect(unverifiedRedirect("/")).toBe("/verify-email");
    expect(unverifiedRedirect("/account")).toBe("/verify-email?next=%2Faccount");
    expect(unverifiedRedirect("/account/favorites/abc")).toBe("/verify-email?next=%2Faccount%2Ffavorites%2Fabc");
  });
  test("登入相關頁、驗證連結落點與條款頁不轉", () => {
    for (const page of ["/verify-email", "/auth/action", "/login", "/register", "/forgot-password", "/privacy", "/terms"]) {
      expect(unverifiedRedirect(page)).toBeNull();
    }
  });
});

describe("Firebase 錯誤", () => {
  test("對應到介面訊息 key", () => {
    expect(authErrorKey("auth/invalid-credential")).toBe("auth.errors.invalidCredentials");
    expect(authErrorKey("auth/email-already-in-use")).toBe("auth.errors.emailInUse");
    expect(authErrorKey("auth/expired-action-code")).toBe("auth.errors.expiredLink");
    expect(authErrorKey("auth/something-new")).toBeNull();
    expect(authErrorKey(undefined)).toBeNull();
  });

  test("彈出視窗被擋時改用頁面導向", () => {
    expect(shouldUseRedirect("auth/popup-blocked")).toBe(true);
    expect(shouldUseRedirect("auth/popup-closed-by-user")).toBe(false);
  });

  test("只輸出 SDK 代碼，不輸出錯誤內容", () => {
    expect(safeErrorCode({ code: "auth/internal-error", message: "token=secret" }, "SIGN_IN")).toBe("auth/internal-error");
    expect(safeErrorCode(new TypeError("x"), "SIGN_IN")).toBe("SIGN_IN_TYPE_ERROR");
    expect(safeErrorCode({ code: "<script>" }, "SIGN_IN")).toBe("SIGN_IN_UNKNOWN_ERROR");
  });
});
