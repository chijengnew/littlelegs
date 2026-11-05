import { Suspense } from "react";
import PlaceDetail from "@/components/PlaceDetail";

export default function PlacePage() {
  return (
    <Suspense>
      <PlaceDetail />
    </Suspense>
  );
}
