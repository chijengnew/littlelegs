import { describe, expect, test } from "vitest";
import { phrases } from "./phrases";

const cut = (text: string) => phrases(text).join("|");

describe("phrases", () => {
  test("拼回去和原文完全相同", () => {
    const text = "LittleLegs 由 CHI 經營，協助家長規劃台灣的親子單日自駕行程：依您填的條件推薦景點，並把 1–5 個景點排成一天的行程。";
    expect(phrases(text).join("")).toBe(text);
  });

  test("單字黏前面、介係詞黏後面，不在詞中間斷開", () => {
    expect(cut("在法律允許的範圍內，因資料不準確或現場狀況改變")).toBe("在法律|允許的|範圍內，|因資料|不準確|或現場|狀況|改變");
    expect(cut("勾選和自訂項目")).toBe("勾選|和自訂|項目");
    expect(cut("滿意度、內容")).toBe("滿意度、|內容");
  });

  test("標點不會出現在行首，括號開頭不會被留在行尾", () => {
    for (const p of phrases("特殊營業時間（例如臨時休館）無法確認。選擇「目前位置」時，包含裝置座標。")) {
      expect("，。、；：）」』》".includes(p[0])).toBe(false);
      expect("（「『《".includes(p.at(-1) ?? "")).toBe(false);
    }
  });

  test("英數字之間不插入換行點", () => {
    expect(cut("Google Maps Platform")).toBe("Google Maps Platform");
    expect(cut("chiiifortest@gmail.com")).toBe("chiiifortest@gmail.com");
  });
});
