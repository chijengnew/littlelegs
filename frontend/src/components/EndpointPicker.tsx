"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { api, type Schemas } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import type { EndpointChoice } from "@/lib/form";
import { uuidv4 } from "@/lib/ids";
import ui from "./ui.module.css";
import s from "./EndpointPicker.module.css";

type Tab = "places" | "google" | "device";
type Props = {
  label: string;
  value: EndpointChoice | null;
  onChange: (v: EndpointChoice | null) => void;
  error?: string;
};

const DEBOUNCE_MS = 300;

export default function EndpointPicker({ label, value, onChange, error }: Props) {
  const t = useTranslations();
  const id = useId();
  const [tab, setTab] = useState<Tab>("places");

  if (value) {
    return (
      <div>
        <span className={ui.label} id={`${id}-l`}>
          {label}
        </span>
        <div className={s.selected} aria-labelledby={`${id}-l`}>
          <span className={s.pin} aria-hidden="true">
            {value.endpoint.type === "device_coordinate" ? "◎" : "●"}
          </span>
          <span className={s.selectedName}>{value.display}</span>
          <button type="button" className={ui.ghost} onClick={() => onChange(null)}>
            {t("endpoint.change")}
          </button>
        </div>
      </div>
    );
  }

  const tabs: { key: Tab; text: string }[] = [
    { key: "places", text: t("endpoint.tabPlaces") },
    { key: "google", text: t("endpoint.tabGoogle") },
    { key: "device", text: t("endpoint.tabDevice") },
  ];

  return (
    <fieldset className={s.fieldset} aria-invalid={Boolean(error)}>
      <legend className={ui.label}>{label}</legend>
      <div className={s.tabs} role="tablist">
        {tabs.map((x) => (
          <button
            key={x.key}
            type="button"
            role="tab"
            id={`${id}-tab-${x.key}`}
            aria-selected={tab === x.key}
            aria-controls={`${id}-panel`}
            className={tab === x.key ? s.tabActive : s.tab}
            onClick={() => setTab(x.key)}
          >
            {x.text}
          </button>
        ))}
      </div>
      <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-tab-${tab}`} className={s.panel}>
        {tab === "places" && <PlaceSearch onPick={onChange} />}
        {tab === "google" && <GoogleSearch onPick={onChange} />}
        {tab === "device" && <DevicePick onPick={onChange} />}
      </div>
      {error && <p className={ui.error}>{t.has(error) ? t(error) : error}</p>}
    </fieldset>
  );
}

function PlaceSearch({ onPick }: { onPick: (v: EndpointChoice) => void }) {
  const t = useTranslations();
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
        const { data, error, response } = await api.POST("/v1/endpoints/places/search", { body: { q: query, limit: 8 } });
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
    <div>
      <input
        className={ui.input}
        type="search"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          if (!e.target.value.trim()) setItems(null);
        }}
        placeholder={t("endpoint.searchPlaceholder")}
        aria-label={t("endpoint.searchPlaceholder")}
        autoComplete="off"
      />
      <div aria-live="polite">
        {err && <p className={ui.error}>{err}</p>}
        {!loading && items?.length === 0 && <p className={ui.hint}>{t("endpoint.noResults")}</p>}
      </div>
      {items && items.length > 0 && (
        <ul className={s.results}>
          {items.map((p) => (
            <li key={p.place_id}>
              <button
                type="button"
                className={s.result}
                onClick={() => onPick({ endpoint: { type: "place_ref", place_id: p.place_id }, display: p.name })}
              >
                <span className={s.resultName}>{p.name}</span>
                <span className={s.resultMeta}>
                  <span className={p.kind === "lodging" ? ui.chipAmber : ui.chipBlue}>
                    {t(p.kind === "lodging" ? "endpoint.lodging" : "endpoint.attraction")}
                  </span>
                  {p.address ?? p.city}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function GoogleSearch({ onPick }: { onPick: (v: EndpointChoice) => void }) {
  const t = useTranslations();
  const [input, setInput] = useState("");
  const [label, setLabel] = useState("");
  const [suggestions, setSuggestions] = useState<Schemas["Suggestion"][]>([]);
  const [attribution, setAttribution] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const session = useRef(uuidv4());
  const seq = useRef(0);

  useEffect(() => {
    const text = input.trim();
    if (text.length < 2) return;
    const my = ++seq.current;
    const timer = setTimeout(async () => {
      try {
        const { data, error, response } = await api.POST("/v1/endpoints/autocomplete", {
          body: { input: text, session_token: session.current },
        });
        if (my !== seq.current) return;
        if (data) {
          setSuggestions(data.suggestions);
          setAttribution(data.attribution);
          setErr(null);
        } else {
          const ue = toUiError(t, error, response.status);
          setErr(ue.limitWindow === "session" ? t("endpoint.sessionLimit") : ue.message);
        }
      } catch (e) {
        if (my === seq.current) setErr(toUiError(t, e).message);
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [input, t]);

  async function pick(sug: Schemas["Suggestion"]) {
    setBusy(true);
    setErr(null);
    try {
      const { data, error, response } = await api.POST("/v1/endpoints/resolve", {
        body: { google_place_id: sug.google_place_id, session_token: session.current },
      });
      session.current = uuidv4();
      if (!data) {
        setErr(toUiError(t, error, response.status).message);
        return;
      }
      if (!data.in_service_area) {
        setErr(t("endpoint.outOfArea"));
        return;
      }
      const trimmed = label.trim().slice(0, 20);
      onPick({
        endpoint: {
          type: "google_place",
          google_place_id: data.google_place_id,
          endpoint_id: data.endpoint_id ?? null,
          label: trimmed || null,
        },
        display: trimmed || t("endpoint.customPlace"),
      });
    } catch (e) {
      setErr(toUiError(t, e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={s.stack}>
      <input
        className={ui.input}
        type="search"
        value={input}
        onChange={(e) => {
          setInput(e.target.value);
          if (e.target.value.trim().length < 2) setSuggestions([]);
        }}
        placeholder={t("endpoint.googlePlaceholder")}
        aria-label={t("endpoint.googlePlaceholder")}
        autoComplete="off"
      />
      <div>
        <label className={ui.hint} htmlFor="ep-label">
          {t("endpoint.labelInput")}
        </label>
        <input
          id="ep-label"
          className={ui.input}
          value={label}
          maxLength={20}
          onChange={(e) => setLabel(e.target.value)}
          placeholder={t("endpoint.labelPlaceholder")}
        />
      </div>
      <div aria-live="polite">{err && <p className={ui.error}>{err}</p>}</div>
      {suggestions.length > 0 && (
        <>
          <ul className={s.results}>
            {suggestions.map((sg) => (
              <li key={sg.google_place_id}>
                <button type="button" className={s.result} disabled={busy} onClick={() => pick(sg)}>
                  <span className={s.resultName}>{sg.text}</span>
                </button>
              </li>
            ))}
          </ul>
          <p className={s.attribution}>{attribution || t("endpoint.googleAttribution")}</p>
        </>
      )}
    </div>
  );
}

function DevicePick({ onPick }: { onPick: (v: EndpointChoice) => void }) {
  const t = useTranslations();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function locate() {
    if (!("geolocation" in navigator)) {
      setErr(t("endpoint.deviceError"));
      return;
    }
    setBusy(true);
    setErr(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setBusy(false);
        const acc = Math.round(pos.coords.accuracy);
        onPick({
          endpoint: {
            type: "device_coordinate",
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
            accuracy_m: acc,
            label: null,
          },
          display: `${t("endpoint.tabDevice")}（±${acc} m）`,
        });
      },
      () => {
        setBusy(false);
        setErr(t("endpoint.deviceError"));
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  }

  return (
    <div>
      <button type="button" className={ui.soft} onClick={locate} disabled={busy}>
        {busy ? t("endpoint.locating") : t("endpoint.useDevice")}
      </button>
      <div aria-live="polite">{err && <p className={ui.error}>{err}</p>}</div>
    </div>
  );
}
