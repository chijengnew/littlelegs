const POINT = /^獨立設施點位「([^」]*)」（[^）]*）/;
const TOILET = /(?:多功能)?(?:無障礙)?親子(?:無障礙)?(?:廁所)?\d*$/;
const EQUIPMENT: [RegExp, string][] = [
  [/尿布臺\s*(\d+)/, "尿布臺"],
  [/兒童座椅\s*(\d+)/, "兒童座椅"],
];
const HOURS =
  /^(週[一二三四五六日])\s*(?:至|~|～)\s*(週[一二三四五六日])\s*(\d{1,2})\s*[:：]\s*(\d{2})\s*[~～]\s*(\d{1,2})\s*[:：]\s*(\d{2})\s*(.*)$/;
const NOON = /^中午開放\s*(?:[(（]([^)）]+)[)）])?$/;
const CODE_ONLY = /^(?:\d+號|[\d-]+|廣\d+|景觀)$/;

function spaced(text: string): string {
  return text
    .replace(/(\p{Script=Han})([A-Za-z0-9])/gu, "$1 $2")
    .replace(/([A-Za-z0-9])(\p{Script=Han})/gu, "$1 $2")
    .replace(/(\d+F)(?=[A-Za-z])/g, "$1 ");
}

function placeOf(raw: string, venue: string): string {
  let where = raw.replace(TOILET, "").trim().replace(/\(/g, "（").replace(/\)/g, "）");
  if (venue && where.startsWith(venue)) where = where.slice(venue.length).trim().replace(/^（(.+)）$/, "$1");
  where = where
    .replace(/(\d+)樓/g, "$1F")
    .replace(/([東西南北])([男女])$/, "$1側$2廁")
    .replace(/([A-Za-z0-9])([東西南北])$/, "$1$2側")
    .replace(/([左右])$/, "$1邊");
  return CODE_ONLY.test(where) ? "" : where;
}

function hoursNote(m: RegExpMatchArray): string {
  const [, from, to, h1, m1, h2, m2, rest] = m;
  const range = `${from}至${to} ${h1.padStart(2, "0")}:${m1}–${h2.padStart(2, "0")}:${m2}`;
  const remark = rest.trim();
  if (!remark) return range;
  const noon = NOON.exec(remark);
  if (noon) return noon[1] ? `${range}（午休照常開放，${noon[1]}）` : `${range}（午休照常開放）`;
  return `${range}，${remark}`;
}

function pointNote(note: string, venue: string): string | null {
  const hours = note.match(HOURS);
  if (hours) return hoursNote(hours);
  const cut = note.lastIndexOf("；");
  const where = placeOf(cut < 0 ? note : note.slice(0, cut), venue);
  const equipment = cut < 0 ? "" : note.slice(cut + 1);
  const items = EQUIPMENT.filter(([re]) => Number(re.exec(equipment)?.[1] ?? 0) > 0).map(([, name]) => name);
  const parts = [where ? spaced(`在${where}`) : "", items.length > 0 ? `有${items.join("、")}` : ""].filter(Boolean);
  return parts.length > 0 ? parts.join("；") : null;
}

export function facilityNote(raw: string | null | undefined): string | null {
  const text = raw?.trim();
  if (!text) return null;
  if (text === "來源記載互相矛盾") return "資料不一致，請出發前向場館確認";
  if (/^friendly 含「哺\(集\)乳友善」$/.test(text)) return "哺（集）乳友善空間";
  if (text === "共融式遊戲場" || text === "特色遊戲場") return text;
  const point = POINT.exec(text);
  return point ? pointNote(text.slice(point[0].length).trim(), point[1]) : null;
}

export function typeNote(raw: string | null | undefined): string | null {
  return raw && /^環境教育設施場所認證/.test(raw.trim()) ? "環境部認證場所" : null;
}

export function displayAddress(address: string | null | undefined): string | null {
  const text = address?.trim().replace(/^\d{3,6}\s*(?=\D)/, "");
  return text || null;
}
