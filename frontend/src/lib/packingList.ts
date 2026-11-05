export type PackingGroup = "basic" | "infant" | "preschool" | "schoolAge" | "nap" | "rain" | "water" | "outdoor";

export type PackingItem = { id: string; labelKey: string };

export type PackingContext = {
  ages: readonly number[];
  hasNap: boolean;
  primaryTypes: readonly (string | null | undefined)[];
  expectRain: boolean;
};

const item = (id: string, labelKey = id): PackingItem => ({ id, labelKey });
const WATER_TYPES = new Set(["beach", "hot_spring"]);
const OUTDOOR_TYPES = new Set(["trail", "nature"]);
const CLOTHES = "spareClothes";

export function buildPackingList(c: PackingContext): { group: PackingGroup; items: PackingItem[] }[] {
  const multi = c.ages.length > 1;
  const clothes = (labelKey: string) => item(CLOTHES, multi ? "spareClothesMulti" : labelKey);
  const has = (min: number, max: number) => c.ages.some((a) => a >= min && a <= max);
  const carSeat = item("carSeat");

  const rules: [PackingGroup, boolean, PackingItem[]][] = [
    [
      "basic",
      true,
      [
        item("healthCard"),
        item("medicine"),
        item("drinkingWater"),
        item("wipes"),
        item("trashBag"),
        ...(c.expectRain ? [] : [item("rainGearOptional")]),
      ],
    ],
    [
      "infant",
      has(0, 2),
      [item("diapers"), item("feeding"), item("babyFood"), item("carrier"), carSeat, clothes("spareClothesInfant")],
    ],
    ["preschool", has(3, 6), [carSeat, clothes("spareClothesChild"), item("snacks"), item("waterBottle"), item("toy")]],
    ["schoolAge", has(7, Number.MAX_SAFE_INTEGER), [item("waterBottle"), item("hat"), item("lightJacket")]],
    ["nap", c.hasNap, [item("blanket"), item("comfortItem")]],
    ["rain", c.expectRain, [item("raincoat"), item("umbrella"), item("spareShoes")]],
    [
      "water",
      c.primaryTypes.some((t) => t && WATER_TYPES.has(t)),
      [item("swimwear"), item("towel"), clothes("spareClothesOne")],
    ],
    [
      "outdoor",
      c.primaryTypes.some((t) => t && OUTDOOR_TYPES.has(t)),
      [item("insectRepellent"), item("sunscreen"), item("walkingShoes")],
    ],
  ];

  const seen = new Set<string>();
  return rules.flatMap(([group, active, items]) => {
    if (!active) return [];
    const unique = items.filter((x) => !seen.has(x.id) && Boolean(seen.add(x.id)));
    return unique.length ? [{ group, items: unique }] : [];
  });
}
