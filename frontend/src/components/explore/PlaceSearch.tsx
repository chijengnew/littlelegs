"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { api, type Schemas } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import { displayAddress } from "@/lib/placeText";
import PlaceArt from "../art/PlaceArt";
import { StampIcon } from "./ExploreArt";
import { stampHref } from "./StampLink";
import ui from "../ui.module.css";
import picker from "../EndpointPicker.module.css";
import s from "./explore.module.css";

const DEBOUNCE_MS = 300;

export default function PlaceSearch() {
  const t = useTranslations();
  const inputId = useId();
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Schemas["PlaceSummary"][] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    const query = q.trim();
    if (!query) return;
    const my = ++seq.current;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const { data, error, response } = await api.POST("/v1/endpoints/places/search", {
          body: { q: query, kind: "attraction", limit: 8 },
        });
        if (my !== seq.current) return;
        if (data) {
          setItems(data.items);
          setErr(null);
        } else setErr(toUiError(t, error, response.status).message);
      } catch (e) {
        if (my === seq.current) setErr(toUiError(t, e).message);
      } finally {
        if (my === seq.current) setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [q, t]);

  return (
    <section className={`${ui.card} ${s.card}`} aria-labelledby="place-search-title">
      <h2 className={s.cardTitle} id="place-search-title">
        <StampIcon size={22} />
        {t("explore.search.title")}
      </h2>
      <p className={s.lead}>{t("explore.search.lead")}</p>
      <div>
        <label htmlFor={inputId} className={ui.label}>{t("explore.search.label")}</label>
        <input
          id={inputId}
          className={ui.input}
          type="search"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            if (!e.target.value.trim()) {
              seq.current += 1;
              setItems(null);
              setErr(null);
              setLoading(false);
            }
          }}
          placeholder={t("explore.search.placeholder")}
          autoComplete="off"
          maxLength={50}
        />
        <div aria-live="polite">
          {err && <p className={ui.error}>{err}</p>}
          {!loading && !err && items?.length === 0 && <p className={ui.hint}>{t("explore.search.noResults")}</p>}
        </div>
        {items && items.length > 0 && (
          <ul className={picker.results}>
            {items.map((p) => (
              <li key={p.place_id}>
                <Link href={stampHref(p.place_id, "passport")} className={`${picker.result} ${s.searchResult}`}>
                  <PlaceArt type={p.primary_type} className={s.searchArt} />
                  <span className={s.searchText}>
                    <span className={picker.resultName}>{p.name}</span>
                    <span className={picker.resultMeta}>
                      {p.primary_type && <span className={ui.chipBlue}>{t(`types.${p.primary_type}`)}</span>}
                      {displayAddress(p.address) ?? p.city}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
