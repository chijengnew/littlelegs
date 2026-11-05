import { z } from "zod";
import type { Schemas } from "./api/client";

export const FEEDBACK_TYPES = ["bug", "place_data", "suggestion", "other"] as const;
const SOURCES = ["planner", "place_detail", "saved_detail", "footer", "other"] as const;
export const MAX_FEEDBACK_LENGTH = 1000;
const UUID7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export type FeedbackType = (typeof FEEDBACK_TYPES)[number];
export type FeedbackContext = { source: (typeof SOURCES)[number]; type: FeedbackType; placeId: string | null };
export type FeedbackValues = { type: FeedbackType; rating: number | null; content: string; email: string };
export type FeedbackErrors = { content?: "required" | "tooLong"; email?: "badEmail" };

export function feedbackContext(params: { get(name: string): string | null }): FeedbackContext {
  const from = params.get("from");
  const type = params.get("type");
  const place = params.get("place");
  return {
    source: SOURCES.find((x) => x === from) ?? "other",
    type: FEEDBACK_TYPES.find((x) => x === type) ?? "bug",
    placeId: place && UUID7.test(place) ? place : null,
  };
}

const schema = z.object({
  content: z.string().trim().min(1, "required").max(MAX_FEEDBACK_LENGTH, "tooLong"),
  email: z.union([z.literal(""), z.string().regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, "badEmail").max(254, "badEmail")]),
});

export function validateFeedback(v: Pick<FeedbackValues, "content" | "email">): FeedbackErrors {
  const r = schema.safeParse({ content: v.content, email: v.email.trim() });
  if (r.success) return {};
  const out: Record<string, string> = {};
  for (const issue of r.error.issues) {
    const key = String(issue.path[0]);
    out[key] ??= key === "email" ? "badEmail" : issue.message;
  }
  return out as FeedbackErrors;
}

export function toFeedbackBody(v: FeedbackValues, c: FeedbackContext): Schemas["FeedbackIn"] {
  const email = v.email.trim();
  return {
    type: v.type,
    rating: v.rating,
    content: v.content.trim(),
    contact_email: email || null,
    source_page: c.source,
    place_id: v.type === "place_data" ? c.placeId : null,
  };
}
