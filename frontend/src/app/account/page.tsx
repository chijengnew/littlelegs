import { Suspense } from "react";
import AccountView from "@/components/auth/AccountView";

export default function Page() {
  return (
    <Suspense>
      <AccountView />
    </Suspense>
  );
}
