const PREFIX = "littlelegs:packing:v1:";
const GUEST = `${PREFIX}guest:`;
const MEMBER = `${PREFIX}member:`;
const ALIAS = `${PREFIX}alias:`;
export const MAX_CUSTOM_ITEMS = 20;
export const MAX_CUSTOM_LENGTH = 40;

export type PackingState = {
  checked: string[];
  removed: string[];
  custom: { id: string; label: string }[];
  expectRain: boolean;
};

export const emptyPacking = (): PackingState => ({ checked: [], removed: [], custom: [], expectRain: false });
export const queryListId = (queryId: string) => `q:${queryId}`;
export const favoriteListId = (favoriteId: string) => `f:${favoriteId}`;

const guestKey = (listId: string) => `${GUEST}${listId}`;
const memberKey = (uid: string, listId: string) => `${MEMBER}${uid}:${listId}`;
const aliasKey = (uid: string, listId: string) => `${ALIAS}${uid}:${listId}`;

const strings = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);

function parse(raw: string | null): PackingState | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw);
    if (!v || typeof v !== "object") return null;
    const custom = Array.isArray(v.custom)
      ? v.custom
          .filter((x: { id?: unknown; label?: unknown }) => typeof x?.id === "string" && typeof x?.label === "string")
          .slice(0, MAX_CUSTOM_ITEMS)
          .map((x: { id: string; label: string }) => ({ id: x.id, label: x.label.slice(0, MAX_CUSTOM_LENGTH) }))
      : [];
    return { checked: strings(v.checked), removed: strings(v.removed), custom, expectRain: v.expectRain === true };
  } catch {
    return null;
  }
}

function keysOf(storage: Storage, prefix: string): string[] {
  const out: string[] = [];
  for (let i = 0; i < storage.length; i++) {
    const k = storage.key(i);
    if (k?.startsWith(prefix)) out.push(k);
  }
  return out;
}

function resolve(uid: string, listId: string): string {
  const target = localStorage.getItem(aliasKey(uid, listId));
  return target?.startsWith("q:") ? target : listId;
}

export function loadPacking(uid: string | null, listId: string): PackingState {
  try {
    const raw = uid ? localStorage.getItem(memberKey(uid, resolve(uid, listId))) : sessionStorage.getItem(guestKey(listId));
    return parse(raw) ?? emptyPacking();
  } catch {
    return emptyPacking();
  }
}

export function savePacking(uid: string | null, listId: string, state: PackingState): void {
  try {
    const raw = JSON.stringify(state);
    if (uid) localStorage.setItem(memberKey(uid, resolve(uid, listId)), raw);
    else sessionStorage.setItem(guestKey(listId), raw);
  } catch {
  }
}

export function adoptGuestPacking(uid: string, listId: string): void {
  try {
    const raw = sessionStorage.getItem(guestKey(listId));
    if (raw === null) return;
    const key = memberKey(uid, resolve(uid, listId));
    if (localStorage.getItem(key) === null) localStorage.setItem(key, raw);
    sessionStorage.removeItem(guestKey(listId));
  } catch {
  }
}

export function linkFavoritePacking(uid: string, favoriteId: string, queryId: string): void {
  try {
    const f = favoriteListId(favoriteId);
    if (localStorage.getItem(aliasKey(uid, f)) !== null || localStorage.getItem(memberKey(uid, f)) !== null) return;
    localStorage.setItem(aliasKey(uid, f), queryListId(queryId));
  } catch {
  }
}

export function removeFavoritePacking(uid: string, favoriteId: string): void {
  try {
    const f = favoriteListId(favoriteId);
    localStorage.removeItem(aliasKey(uid, f));
    localStorage.removeItem(memberKey(uid, f));
  } catch {
  }
}

export function removeHistoryPacking(uid: string, queryId: string): void {
  try {
    const q = queryListId(queryId);
    const raw = localStorage.getItem(memberKey(uid, q));
    const prefix = `${ALIAS}${uid}:`;
    for (const k of keysOf(localStorage, prefix)) {
      if (localStorage.getItem(k) !== q) continue;
      if (raw !== null) localStorage.setItem(memberKey(uid, k.slice(prefix.length)), raw);
      localStorage.removeItem(k);
    }
    localStorage.removeItem(memberKey(uid, q));
  } catch {
  }
}

export function purgeOtherMembers(uid: string | null): void {
  try {
    const keep = uid ? [`${MEMBER}${uid}:`, `${ALIAS}${uid}:`] : [];
    for (const k of [...keysOf(localStorage, MEMBER), ...keysOf(localStorage, ALIAS)]) {
      if (!keep.some((p) => k.startsWith(p))) localStorage.removeItem(k);
    }
  } catch {
  }
}

export function clearGuestPacking(): void {
  try {
    for (const k of keysOf(sessionStorage, GUEST)) sessionStorage.removeItem(k);
  } catch {
  }
}
