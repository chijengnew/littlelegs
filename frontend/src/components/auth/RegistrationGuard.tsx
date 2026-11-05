"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { unverifiedRedirect } from "@/lib/authFlow";
import { useAuth } from "../AuthProvider";

export default function RegistrationGuard() {
  const { unverified } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    const target = unverified ? unverifiedRedirect(pathname) : null;
    if (target) router.replace(target);
  }, [unverified, pathname, router]);

  return null;
}
