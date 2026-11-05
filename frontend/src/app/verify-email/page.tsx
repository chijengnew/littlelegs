import { Suspense } from "react";
import VerifyEmail from "@/components/auth/VerifyEmail";

export default function Page() {
  return (
    <Suspense>
      <VerifyEmail />
    </Suspense>
  );
}
