import { Children, cloneElement, isValidElement, type ReactNode } from "react";

const segmenter = new Intl.Segmenter("zh-Hant", { granularity: "word" });
const HAN = /\p{Script=Han}/u;
const CLOSE = new Set([..."，。、；：！？）」』》〉／"]);
const BRACKET_CLOSE = new Set([..."）」』》〉"]);
const OPEN = new Set([..."（「『《〈"]);
const LEADING = new Set([..."和與或及在依由把被從向對給但並而因如若只不也都就會可該每各請讓將已再才還最很太更仍"]);
const INLINE = new Set(["span", "a", "strong", "em", "b", "i"]);

function canBreak(a: string, b: string): boolean {
  const last = a.at(-1) ?? "";
  const first = b[0] ?? "";
  if (!last || !first || /\s/.test(last) || /\s/.test(first)) return false;
  if (CLOSE.has(first) || OPEN.has(last)) return false;
  if (CLOSE.has(last)) return !(BRACKET_CLOSE.has(last) && b.length === 1 && HAN.test(b) && !LEADING.has(b));
  if (OPEN.has(first)) return true;
  if (!HAN.test(last) || !HAN.test(first)) return false;
  if (a.length === 1 && LEADING.has(a)) return false;
  if (b.length === 1 && !LEADING.has(b)) return false;
  return true;
}

function segments(text: string): string[] {
  return [...segmenter.segment(text)].map((s) => s.segment);
}

export function phrases(text: string): string[] {
  const out: string[] = [];
  let prev = "";
  for (const seg of segments(text)) {
    if (!out.length || canBreak(prev, seg)) out.push("");
    out[out.length - 1] += seg;
    prev = seg;
  }
  return out;
}

function textOf(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (isValidElement<{ children?: ReactNode }>(node)) return textOf(node.props.children);
  return "";
}

function isInline(node: ReactNode): boolean {
  if (typeof node === "string" || typeof node === "number") return true;
  return isValidElement(node) && (typeof node.type === "function" || INLINE.has(node.type as string));
}

function breakText(text: string): ReactNode {
  const parts = phrases(text);
  if (parts.length < 2) return text;
  return parts.flatMap((p, i) => (i ? [<wbr key={i} />, p] : [p]));
}

export function phrased(node: ReactNode, keepClass?: string): ReactNode {
  if (typeof node === "string") return breakText(node);
  if (!isValidElement<{ children?: ReactNode; className?: string }>(node) || node.props.children == null) return node;
  if (keepClass && node.props.className === keepClass) return node;
  const kids = Children.toArray(node.props.children);
  const out: ReactNode[] = [];
  kids.forEach((kid, i) => {
    const prev = kids[i - 1];
    if (i && isInline(prev) && isInline(kid)) {
      const a = segments(textOf(prev)).at(-1) ?? "";
      const b = segments(textOf(kid))[0] ?? "";
      if (canBreak(a, b)) out.push(<wbr key={`b${i}`} />);
    }
    out.push(phrased(kid, keepClass));
  });
  return cloneElement(node, undefined, ...out);
}
