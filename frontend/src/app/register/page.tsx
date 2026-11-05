import { Suspense } from "react";
import RegisterForm from "@/components/auth/RegisterForm";

export default function Page() {
  return (
    <Suspense>
      <RegisterForm />
    </Suspense>
  );
}
