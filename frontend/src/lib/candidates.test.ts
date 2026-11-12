import { describe, expect, test } from "vitest";
import type { Candidate } from "./api/client";
import { areaOf, ownWarnings, sharedWarnings } from "./candidates";

const W = {
  hoursLater: { code: "hours_checked_when_planning", message: "營業時間會在排序或檢查行程時確認" },
  hoursUnknown: { code: "hours_unknown", message: "營業時間未確認，請出發前自行確認" },
  stay: { code: "stay_estimated", message: "停留時間為估計值" },
  indoor: { code: "indoor_inferred", message: "室內屬性依類型推定，非場勘確認" },
};

const cand = (place_id: string, warnings: Candidate["warnings"]) => ({ place_id, warnings }) as Candidate;

describe("候選卡片的不確定性提醒", () => {
  test("每個候選都有的提醒只在列表上方顯示一次，卡片只顯示自己特有的", () => {
    const a = cand("a", [W.hoursLater, W.hoursUnknown, W.stay]);
    const b = cand("b", [W.hoursLater, W.stay]);
    const shared = sharedWarnings([a, b]);
    expect(shared.map((w) => w.code)).toEqual(["hours_checked_when_planning"]);
    expect(ownWarnings(a, shared).map((w) => w.code)).toEqual(["hours_unknown"]);
    expect(ownWarnings(b, shared)).toEqual([]);
  });

  test("已用標籤呈現的「停留估計」與「室內推定」不重複列出；只有 1 個候選時全部留在卡片上", () => {
    const a = cand("a", [W.hoursLater, W.indoor, W.stay]);
    expect(sharedWarnings([a])).toEqual([]);
    expect(ownWarnings(a, []).map((w) => w.code)).toEqual(["hours_checked_when_planning"]);
  });
});

describe("areaOf", () => {
  test("三種地址寫法都只留下縣市與鄉鎮市區", () => {
    expect(areaOf("115 臺北市南港區研究院路二段128號")).toBe("臺北市南港區");
    expect(areaOf("116臺北市文山區新光路二段30號")).toBe("臺北市文山區");
    expect(areaOf("新北市石碇區碇格路一段")).toBe("新北市石碇區");
    expect(areaOf("302新竹縣竹北市縣政九路")).toBe("新竹縣竹北市");
    expect(areaOf("嘉義市東區忠孝路")).toBe("嘉義市東區");
  });

  test("地址認不出縣市時改用城市欄位，都沒有就不顯示", () => {
    expect(areaOf("中山路一段1號", "臺南市")).toBe("臺南市");
    expect(areaOf(null, null)).toBeNull();
  });
});
