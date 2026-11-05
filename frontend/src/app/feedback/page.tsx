import { Suspense } from "react";
import FeedbackForm from "@/components/FeedbackForm";

export default function Page() {
  return (
    <Suspense>
      <FeedbackForm />
    </Suspense>
  );
}
