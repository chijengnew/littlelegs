import { Suspense } from "react";
import SavedDetail from "@/components/account/SavedDetail";

export default function Page() {
  return (
    <Suspense>
      <SavedDetail kind="favorite" />
    </Suspense>
  );
}
