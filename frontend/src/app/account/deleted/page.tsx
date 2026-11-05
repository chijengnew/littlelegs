import { Suspense } from "react";
import AccountDeleted from "@/components/account/AccountDeleted";

export default function Page() {
  return (
    <Suspense>
      <AccountDeleted />
    </Suspense>
  );
}
