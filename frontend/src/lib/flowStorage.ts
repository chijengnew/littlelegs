import type { FormState } from "./form";
import { clearGuestPacking } from "./packingStorage";

const KEY = "littlelegs:flow:v1";

export type StoredFlow = {
  form: FormState;
  queryId: string | null;
  submittedKey: string | null;
  selection: { place_id: string; name: string; stay_minutes: number | null; default_stay_minutes?: number }[];
  ownerUid?: string | null;
  searched?: boolean;
  ordered?: boolean;
  step?: "conditions" | "candidates" | "plan";
  planMode?: "sort" | "check";
  dirty?: boolean;
};

export function loadFlow(): StoredFlow | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as StoredFlow;
    if (!v || typeof v !== "object" || !v.form || !Array.isArray(v.selection)) return null;
    return v;
  } catch {
    return null;
  }
}

export function saveFlow(v: StoredFlow): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(v));
  } catch {
  }
}

export function clearFlow(): void {
  try {
    sessionStorage.removeItem(KEY);
    clearGuestPacking();
  } catch {
  }
}
