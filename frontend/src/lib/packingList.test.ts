import { describe, expect, test } from "vitest";
import { buildPackingList, type PackingContext } from "./packingList";

const base: PackingContext = { ages: [4], hasNap: false, primaryTypes: [], expectRain: false };
const build = (c: Partial<PackingContext>) => buildPackingList({ ...base, ...c });
const groups = (c: Partial<PackingContext>) => build(c).map((g) => g.group);
const ids = (c: Partial<PackingContext>) => build(c).flatMap((g) => g.items.map((x) => x.id));
const labels = (c: Partial<PackingContext>) => build(c).flatMap((g) => g.items.map((x) => x.labelKey));

describe("年齡", () => {
  test.each([
    [0, "infant"],
    [2, "infant"],
    [3, "preschool"],
    [6, "preschool"],
    [7, "schoolAge"],
    [18, "schoolAge"],
  ])("%i 歲屬於 %s", (age, group) => {
    expect(groups({ ages: [age] })).toEqual(["basic", group]);
  });

  test("多位孩子同時涵蓋各年齡，不是只看第一位", () => {
    expect(groups({ ages: [1, 5] })).toEqual(["basic", "infant", "preschool"]);
    expect(groups({ ages: [5, 1] })).toEqual(["basic", "infant", "preschool"]);
    expect(ids({ ages: [1, 5] })).toEqual(expect.arrayContaining(["diapers", "snacks"]));
  });

  test("合併時同一項目只列一次", () => {
    const all = ids({ ages: [1, 5, 9], primaryTypes: ["beach"] });
    expect(new Set(all).size).toBe(all.length);
    expect(all.filter((x) => x === "spareClothes")).toHaveLength(1);
    expect(all.filter((x) => x === "waterBottle")).toHaveLength(1);
    expect(all.filter((x) => x === "carSeat")).toHaveLength(1);
  });

  test("替換衣物：一位孩子依年齡給套數，多位孩子依人數準備", () => {
    expect(labels({ ages: [1] })).toContain("spareClothesInfant");
    expect(labels({ ages: [4] })).toContain("spareClothesChild");
    expect(labels({ ages: [1, 1] })).toContain("spareClothesMulti");
    expect(labels({ ages: [1, 5] })).not.toContain("spareClothesInfant");
  });
});

describe("行程條件", () => {
  test("基本用品一定有；常備藥與雨具不暗示每次都必須", () => {
    const basic = build({})[0];
    expect(basic.group).toBe("basic");
    expect(basic.items.map((x) => x.id)).toEqual(expect.arrayContaining(["medicine", "rainGearOptional"]));
  });

  test("午睡才有午睡用品", () => {
    expect(groups({ hasNap: true })).toContain("nap");
    expect(groups({ hasNap: false })).not.toContain("nap");
  });

  test("只有勾選預計會下雨才顯示雨天用品，並取代選用的雨具", () => {
    expect(groups({})).not.toContain("rain");
    expect(groups({ expectRain: true })).toContain("rain");
    expect(ids({ expectRain: true })).not.toContain("rainGearOptional");
  });

  test.each(["beach", "hot_spring"])("%s 顯示海灘、溫泉用品", (type) => {
    expect(groups({ primaryTypes: [type] })).toContain("water");
  });

  test.each(["trail", "nature"])("%s 顯示步道、自然風景用品", (type) => {
    expect(groups({ primaryTypes: [type] })).toContain("outdoor");
  });

  test("其他類型或沒有類型不多加提醒", () => {
    expect(groups({ primaryTypes: ["museum", null, undefined] })).toEqual(["basic", "preschool"]);
  });

  test("7 歲以上去海灘也有替換衣物；已在年齡規則列過就不重複", () => {
    expect(ids({ ages: [9], primaryTypes: ["beach"] })).toContain("spareClothes");
    const water = build({ ages: [4], primaryTypes: ["beach"] }).find((g) => g.group === "water");
    expect(water?.items.map((x) => x.id)).toEqual(["swimwear", "towel"]);
  });
});
