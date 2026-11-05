import { Suspense } from "react";
import EmailAction from "@/components/auth/EmailAction";

export default function Page() {
  return (
    <Suspense>
      <EmailAction />
    </Suspense>
  );
}
