"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import PlaceArt from "./art/PlaceArt";
import type { EditStop } from "./PlanView";
import { CloseIcon } from "./icons";
import ui from "./ui.module.css";
import s from "./SelectionBar.module.css";

type Props = {
  selection: EditStop[];
  types: Record<string, string | null>;
  busy: boolean;
  sorting: boolean;
  limitHit: boolean;
  onRemove: (placeId: string) => void;
  onSort: () => void;
};

export default function SelectionBar({ selection, types, busy, sorting, limitHit, onRemove, onSort }: Props) {
  const t = useTranslations("candidates");
  const dialog = useRef<HTMLDialogElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const viewBtn = useRef<HTMLButtonElement>(null);
  const count = useRef<HTMLElement>(null);
  const chips = useRef<HTMLUListElement>(null);
  const pendingFocus = useRef<string | null>(null);
  const n = selection.length;

  useEffect(() => {
    const id = pendingFocus.current;
    if (!id) return;
    pendingFocus.current = null;
    const next = chips.current?.querySelector<HTMLButtonElement>(`[data-id="${CSS.escape(id)}"]`);
    (next ?? count.current)?.focus();
  }, [selection]);

  const open = () => {
    dialog.current?.showModal();
    title.current?.focus();
  };
  const close = () => dialog.current?.close();
  const removeChip = (id: string) => {
    const i = selection.findIndex((x) => x.place_id === id);
    pendingFocus.current = (selection[i + 1] ?? selection[i - 1])?.place_id ?? "none";
    onRemove(id);
  };

  return (
    <>
      <div className={s.bar}>
        <p className="visually-hidden" role="status">
          {limitHit ? t("limitNotice") : ""}
        </p>
        {limitHit && (
          <p className={s.limit} aria-hidden="true">
            {t("limitNotice")}
          </p>
        )}
        <div className={s.info}>
          <strong ref={count} tabIndex={-1} className={s.count}>
            {t("selected", { n })}
          </strong>
          {n === 0 && <span className={s.hint}>{t("sortHint")}</span>}
        </div>
        {n > 0 && (
          <ul className={s.chips} ref={chips} aria-label={t("chipsLabel")}>
            {selection.map((x) => (
              <li key={x.place_id} className={s.chip} title={x.name}>
                <span className={s.chipName}>{x.name}</span>
                <button
                  type="button"
                  className={s.chipRemove}
                  data-id={x.place_id}
                  disabled={busy}
                  onClick={() => removeChip(x.place_id)}
                  aria-label={t("unselect", { name: x.name })}
                >
                  <CloseIcon size={16} />
                </button>
              </li>
            ))}
          </ul>
        )}
        {n > 0 && (
          <button type="button" ref={viewBtn} className={`${ui.secondary} ${s.view}`} aria-haspopup="dialog" onClick={open}>
            {t("view")}
          </button>
        )}
        <button type="button" className={`${ui.primary} ${s.sort}`} disabled={n === 0 || busy} aria-busy={sorting} onClick={onSort}>
          {t("sort")}
        </button>
      </div>

      <dialog
        ref={dialog}
        className={s.drawer}
        aria-labelledby="selection-title"
        onClose={() => (viewBtn.current ?? count.current)?.focus()}
        onClick={(e) => {
          if (e.target === dialog.current) close();
        }}
      >
        <div className={s.sheet}>
          <div className={s.sheetHead}>
            <h2 id="selection-title" ref={title} tabIndex={-1} className={s.sheetTitle}>
              {t("manageTitle", { n })}
            </h2>
            <button type="button" className={`${ui.iconQuiet} ${s.close}`} onClick={close} aria-label={t("close")}>
              <CloseIcon />
            </button>
          </div>
          {n === 0 ? (
            <p className={ui.hint}>{t("manageEmpty")}</p>
          ) : (
            <ul className={s.picked}>
              {selection.map((x) => (
                <li key={x.place_id}>
                  <PlaceArt type={types[x.place_id]} className={s.pickedArt} />
                  <span className={s.pickedName}>{x.name}</span>
                  <button
                    type="button"
                    className={ui.ghost}
                    disabled={busy}
                    onClick={() => onRemove(x.place_id)}
                    aria-label={t("unselect", { name: x.name })}
                  >
                    {t("unselectShort")}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <button type="button" className={`${ui.primary} ${s.sheetSort}`} disabled={n === 0 || busy} onClick={() => { close(); onSort(); }}>
            {t("sort")}
          </button>
        </div>
      </dialog>
    </>
  );
}
