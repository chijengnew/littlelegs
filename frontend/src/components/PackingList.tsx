"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { uuidv7 } from "@/lib/ids";
import { buildPackingList } from "@/lib/packingList";
import {
  MAX_CUSTOM_ITEMS,
  MAX_CUSTOM_LENGTH,
  adoptGuestPacking,
  loadPacking,
  savePacking,
  type PackingState,
} from "@/lib/packingStorage";
import { useAuth } from "./AuthProvider";
import ui from "./ui.module.css";
import s from "./PackingList.module.css";

type Props = {
  listId: string;
  ages: readonly number[];
  hasNap: boolean;
  primaryTypes: readonly (string | null | undefined)[];
  className?: string;
};

export default function PackingList({ listId, ages, hasNap, primaryTypes, className = "" }: Props) {
  const t = useTranslations("packing");
  const auth = useAuth();
  const ready = auth.booted && !auth.pending;
  const owner = auth.member && auth.user ? auth.user.uid : null;
  const [loaded, setLoaded] = useState<{ key: string; state: PackingState } | null>(null);
  const [draft, setDraft] = useState("");
  const key = `${owner ?? ""}|${listId}`;

  useEffect(() => {
    if (!ready) return;
    if (owner) adoptGuestPacking(owner, listId);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoaded({ key, state: loadPacking(owner, listId) });
  }, [ready, owner, listId, key]);

  const state = loaded?.key === key ? loaded.state : null;
  const expectRain = state?.expectRain ?? false;
  const groups = useMemo(
    () => buildPackingList({ ages, hasNap, primaryTypes, expectRain }),
    [ages, hasNap, primaryTypes, expectRain],
  );
  if (!state) return null;

  function update(next: PackingState) {
    setLoaded({ key, state: next });
    savePacking(owner, listId, next);
  }
  const current = state;
  const toggle = (id: string) =>
    update({
      ...current,
      checked: current.checked.includes(id) ? current.checked.filter((x) => x !== id) : [...current.checked, id],
    });
  const remove = (id: string) => update({ ...current, removed: [...current.removed, id] });
  const removeCustom = (id: string) =>
    update({
      ...current,
      custom: current.custom.filter((x) => x.id !== id),
      checked: current.checked.filter((x) => x !== id),
    });

  function add(e: FormEvent) {
    e.preventDefault();
    const label = draft.trim().slice(0, MAX_CUSTOM_LENGTH);
    if (!label || current.custom.length >= MAX_CUSTOM_ITEMS) return;
    setDraft("");
    if (!current.custom.some((x) => x.label === label)) {
      update({ ...current, custom: [...current.custom, { id: `c:${uuidv7()}`, label }] });
    }
  }

  const visible = groups
    .map((g) => ({ ...g, items: g.items.filter((x) => !current.removed.includes(x.id)) }))
    .filter((g) => g.items.length > 0);
  const ids = [...visible.flatMap((g) => g.items.map((x) => x.id)), ...current.custom.map((x) => x.id)];
  const done = ids.filter((id) => current.checked.includes(id)).length;
  const row = (id: string, label: string, onRemove: () => void) => (
    <li key={id} className={s.item}>
      <label className={s.check}>
        <input type="checkbox" checked={current.checked.includes(id)} onChange={() => toggle(id)} />
        <span>{label}</span>
      </label>
      <button type="button" className={ui.icon} onClick={onRemove} aria-label={t("remove", { name: label })}>
        ×
      </button>
    </li>
  );

  return (
    <section className={`${ui.card} ${s.card} ${className}`} aria-labelledby="packing-title">
      <div className={s.head}>
        <h2 className={ui.cardTitle} id="packing-title" style={{ margin: 0 }}>
          {t("title")}
        </h2>
        <span className={ui.chip}>{t("progress", { done, total: ids.length })}</span>
      </div>
      <p className={ui.hint} style={{ margin: 0 }}>
        {t("hint")}
      </p>
      <label className={s.check}>
        <input
          type="checkbox"
          checked={current.expectRain}
          onChange={(e) => update({ ...current, expectRain: e.target.checked })}
        />
        <span>{t("expectRain")}</span>
      </label>
      {visible.map((g) => (
        <div key={g.group}>
          <h3 className={s.groupTitle}>{t(`groups.${g.group}`)}</h3>
          <ul className={s.items}>{g.items.map((x) => row(x.id, t(`items.${x.labelKey}`), () => remove(x.id)))}</ul>
        </div>
      ))}
      {current.custom.length > 0 && (
        <div>
          <h3 className={s.groupTitle}>{t("groups.custom")}</h3>
          <ul className={s.items}>{current.custom.map((x) => row(x.id, x.label, () => removeCustom(x.id)))}</ul>
        </div>
      )}
      {current.removed.length > 0 && (
        <button
          type="button"
          className={ui.soft}
          style={{ justifySelf: "start" }}
          onClick={() => update({ ...current, removed: [] })}
        >
          {t("restore", { n: current.removed.length })}
        </button>
      )}
      <form className={s.addForm} onSubmit={add}>
        <label className="visually-hidden" htmlFor={`packing-add-${listId}`}>
          {t("customLabel")}
        </label>
        <input
          id={`packing-add-${listId}`}
          className={ui.input}
          value={draft}
          maxLength={MAX_CUSTOM_LENGTH}
          placeholder={t("customPlaceholder")}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button type="submit" className={ui.soft} disabled={!draft.trim() || current.custom.length >= MAX_CUSTOM_ITEMS}>
          {t("add")}
        </button>
      </form>
      <p className={ui.hint} style={{ margin: 0 }}>
        {t(owner ? "storageMember" : "storageGuest")}
      </p>
    </section>
  );
}
