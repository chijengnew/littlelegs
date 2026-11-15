import { describe, expect, test } from "vitest";
import messages from "../../../messages/zh-TW.json";
import { toUiError } from "./problem";

function t(key: string): string {
  const value = key.split(".").reduce<unknown>((node, part) => (node as Record<string, unknown>)?.[part], messages);
  if (typeof value !== "string") throw new Error(`missing message ${key}`);
  return value;
}

describe("後端錯誤改用網站自己的文字", () => {
  test("欄位格式不合法：不顯示後端原文與 Value error 前綴", () => {
    const ue = toUiError(t, {
      status: 422,
      code: "VALIDATION_FAILED",
      detail: "輸入欄位不合法",
      errors: [{ loc: ["body", "conditions", "depart_time"], msg: "Value error, 時間必須是 15 分鐘刻度", type: "value_error" }],
    });
    expect(ue.message).toBe("有欄位格式不正確，請檢查後再送出。");
    expect(ue.fieldErrors).toEqual([{ loc: "conditions.depart_time", msg: "請檢查這個欄位" }]);
  });

  test.each([
    ["DEPARTURE_PASSED", 409, "出發時間已過，請選擇新的時間。"],
    ["OUT_OF_SERVICE_AREA", 422, "起點或終點不在台灣服務範圍內，請重新選擇。"],
    ["ENDPOINT_NOT_FOUND", 422, "找不到此地點，請重新選擇。"],
    ["REAUTH_REQUIRED", 401, "請重新登入後 5 分鐘內再刪除帳號。"],
    ["EMAIL_NOT_VERIFIED", 403, "完成電子郵件驗證後才能使用會員功能。"],
  ])("%s 顯示網站自己的文字", (code, status, text) => {
    expect(toUiError(t, { status, code, detail: "後端原文" }).message).toBe(text);
  });

  test("其他錯誤沿用後端說明，欄位訊息不改", () => {
    const ue = toUiError(t, { status: 409, code: "OPERATION_EXPIRED", detail: "此查詢的操作期限已過，請建立新查詢", errors: [{ loc: ["stops", "0"], msg: "x" }] });
    expect(ue.message).toBe("此查詢的操作期限已過，請建立新查詢");
    expect(ue.fieldErrors).toEqual([{ loc: "stops.0", msg: "x" }]);
  });
});
