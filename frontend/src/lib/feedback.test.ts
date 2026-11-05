import { describe, expect, test } from "vitest";
import { feedbackContext, toFeedbackBody, validateFeedback, type FeedbackContext } from "./feedback";

const params = (q: string) => new URLSearchParams(q);
const PLACE = "0190a000-0000-7000-8000-000000000002";

describe("網址參數", () => {
  test("只接受固定的頁面類型", () => {
    expect(feedbackContext(params("from=footer")).source).toBe("footer");
    expect(feedbackContext(params("from=saved_detail")).source).toBe("saved_detail");
    expect(feedbackContext(params("from=/account/favorites/abc?x=1")).source).toBe("other");
    expect(feedbackContext(params("")).source).toBe("other");
  });

  test("回饋類型與景點編號不合法時不採用", () => {
    expect(feedbackContext(params("type=place_data&place=" + PLACE))).toMatchObject({ type: "place_data", placeId: PLACE });
    expect(feedbackContext(params("type=hack&place=not-a-uuid"))).toMatchObject({ type: "bug", placeId: null });
  });
});

describe("驗證", () => {
  test("內容必填且最多 1,000 字（去掉前後空白後計算）", () => {
    expect(validateFeedback({ content: "   ", email: "" }).content).toBe("required");
    expect(validateFeedback({ content: "字".repeat(1000), email: "" }).content).toBeUndefined();
    expect(validateFeedback({ content: "字".repeat(1001), email: "" }).content).toBe("tooLong");
  });

  test("信箱選填，填了就檢查格式", () => {
    expect(validateFeedback({ content: "好", email: "" })).toEqual({});
    expect(validateFeedback({ content: "好", email: " a@example.com " })).toEqual({});
    expect(validateFeedback({ content: "好", email: "not-an-email" }).email).toBe("badEmail");
    expect(validateFeedback({ content: "好", email: `${"a".repeat(250)}@b.co` }).email).toBe("badEmail");
  });
});

describe("送出內容", () => {
  const ctx: FeedbackContext = { source: "place_detail", type: "place_data", placeId: PLACE };

  test("景點編號只跟著景點資料錯誤回報", () => {
    const base = { rating: null, content: " 地址錯了 ", email: "" };
    expect(toFeedbackBody({ ...base, type: "place_data" }, ctx)).toEqual({
      type: "place_data",
      rating: null,
      content: "地址錯了",
      contact_email: null,
      source_page: "place_detail",
      place_id: PLACE,
    });
    expect(toFeedbackBody({ ...base, type: "suggestion" }, ctx).place_id).toBeNull();
  });
});
