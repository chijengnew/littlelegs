"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { safeNext, withNext } from "@/lib/authFlow";
import { useAuth } from "../AuthProvider";

type Options = {
  hold?: boolean;
  memberTarget?: string;
  verifyPage?: boolean;
};

export function useAuthPage({ hold = false, memberTarget, verifyPage = false }: Options = {}) {
  const auth = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));

  useEffect(() => {
    if (hold) return;
    if (auth.member) router.replace(memberTarget ?? next);
    else if (auth.unverified && !verifyPage) router.replace(withNext("/verify-email", next));
  }, [auth.member, auth.unverified, hold, memberTarget, next, router, verifyPage]);

  return { auth, next, router };
}

export function continueUrl(page: string, next: string): string {
  return `${window.location.origin}${withNext(page, next)}`;
}
