import { describe, expect, test } from "vitest";
import messages from "../../../messages/zh-TW.json";
import { TYPE_ORDER } from "./PlaceArt";

describe("類型圖示", () => {
  test("38 種景點類型（含其他景點）都有自己的圖示，其中 37 種各有不同底色", () => {
    const types = Object.keys(messages.types);
    expect(types).toHaveLength(38);
    expect([...TYPE_ORDER, "other"].sort()).toEqual([...types].sort());
    expect(new Set(TYPE_ORDER).size).toBe(37);
  });
});
