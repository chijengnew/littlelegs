"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import type { Schemas } from "@/lib/api/client";
import { boundsOf, type EndpointTitles, type MapPoint, type MapScene } from "@/lib/mapData";
import { isMapConfigured, loadMaps, mapId, onMapAuthFailure, type GMap, type GMarker, type GPolyline, type Libraries } from "@/lib/maps";
import { useAuth } from "./AuthProvider";
import { LockedMap } from "./SidePanels";
import s from "./MemberMap.module.css";

const PIN_CLASS: Record<MapPoint["kind"], string> = {
  start: s.pinStart,
  end: s.pinEnd,
  start_end: s.pinStartEnd,
  stop: s.pinStop,
  candidate: s.pinCandidate,
};
const Z: Record<MapPoint["kind"], number> = { start: 30, end: 30, start_end: 30, stop: 20, candidate: 10 };

type Props = {
  hints: Schemas["MapHints"] | undefined;
  scene: MapScene | null;
  legend?: "candidates" | "plan";
};

export default function MapPanel({ hints, scene, legend }: Props) {
  const { member } = useAuth();
  if (!member) return <LockedMap variant="locked" message={hints?.message} />;
  if (hints && hints.mode !== "google_map") return <LockedMap variant="stale" />;
  if (!isMapConfigured()) return <LockedMap variant="pending" />;
  return <MemberMap scene={hints ? scene : null} lineNote={hints?.connect_line && scene?.path ? hints.line_note : null} legend={legend} />;
}

export function useEndpointTitles(): EndpointTitles {
  const t = useTranslations("map");
  return useMemo(() => ({ start: t("start"), end: t("end"), startEnd: t("startEnd") }), [t]);
}

function MemberMap({ scene, lineNote, legend }: { scene: MapScene | null; lineNote?: string | null; legend?: Props["legend"] }) {
  const t = useTranslations("map");
  const box = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLDivElement>(null);
  const live = useRef<{ libs: Libraries; map: GMap } | null>(null);
  const drawn = useRef<{ markers: GMarker[]; line: GPolyline | null; keys: string }>({ markers: [], line: null, keys: "" });
  const [visible, setVisible] = useState(false);
  const [state, setState] = useState<"idle" | "ready" | "error">("idle");
  const hasPoints = (scene?.points.length ?? 0) > 0;

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          io.disconnect();
        }
      },
      { rootMargin: "200px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => onMapAuthFailure(() => setState("error")), []);

  useEffect(() => {
    if (!visible || !hasPoints || live.current) return;
    let cancelled = false;
    loadMaps()
      .then((libs) => {
        if (cancelled || !canvas.current) return;
        const map = new libs.maps.Map(canvas.current, {
          mapId,
          center: { lat: 25.04, lng: 121.56 },
          zoom: 12,
          gestureHandling: "cooperative",
          clickableIcons: false,
          mapTypeControl: false,
          streetViewControl: false,
        });
        live.current = { libs, map };
        setState("ready");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [visible, hasPoints]);

  useEffect(() => {
    const m = live.current;
    if (state !== "ready" || !m || !scene) return;
    const d = drawn.current;
    d.markers.forEach((x) => (x.map = null));
    d.line?.setMap(null);
    d.markers = scene.points.map((p) => {
      const el = document.createElement("div");
      el.className = PIN_CLASS[p.kind] + (p.selected ? ` ${s.pinSelected}` : "");
      el.textContent = p.glyph;
      return new m.libs.marker.AdvancedMarkerElement({
        map: m.map,
        position: { lat: p.lat, lng: p.lng },
        content: el,
        title: p.title,
        zIndex: p.selected ? 15 : Z[p.kind],
      });
    });
    d.line = scene.path
      ? new m.libs.maps.Polyline({
          map: m.map,
          path: scene.path,
          geodesic: false,
          clickable: false,
          strokeOpacity: 0,
          icons: [{ icon: { path: "M 0,-1 0,1", strokeOpacity: 0.9, strokeColor: "#1877f2", scale: 3 }, offset: "0", repeat: "14px" }],
        })
      : null;
    const keys = scene.points.map((p) => p.key).join("|");
    if (keys !== d.keys) {
      d.keys = keys;
      const b = boundsOf(scene.points);
      if (scene.points.length === 1 && b) {
        m.map.setCenter({ lat: b.north, lng: b.east });
        m.map.setZoom(14);
      } else if (b) {
        m.map.fitBounds(b, 40);
      }
    }
  }, [state, scene]);

  useEffect(() => {
    const d = drawn.current;
    return () => {
      d.markers.forEach((x) => (x.map = null));
      d.line?.setMap(null);
    };
  }, []);

  const loading = state === "idle" && (!scene || (visible && hasPoints));
  return (
    <section className={s.wrap} aria-label={t("title")} ref={box}>
      <div className={s.canvas}>
        <div ref={canvas} style={{ position: "absolute", inset: 0 }} aria-hidden={state !== "ready"} />
        {state === "error" && (
          <div className={s.status} role="status">
            <strong>{t("errorTitle")}</strong>
            <span>{t("errorBody")}</span>
          </div>
        )}
        {loading && (
          <div className={s.status} role="status">
            {t("loading")}
          </div>
        )}
        {state === "idle" && scene && !hasPoints && (
          <div className={s.status} role="status">
            {t("empty")}
          </div>
        )}
      </div>
      {(legend || lineNote) && (
        <div className={s.foot}>
          {legend && (
            <ul className={s.legend}>
              {legend === "candidates" ? (
                <>
                  <Legend cls={s.pinStart} label={t("legendStart")} />
                  <Legend cls={s.pinEnd} label={t("legendEnd")} />
                  <Legend cls={s.pinCandidate} label={t("legendCandidate")} />
                  <Legend cls={s.pinSelected} label={t("legendSelected")} />
                </>
              ) : (
                <>
                  <Legend cls={s.pinStart} label={t("legendStart")} />
                  <Legend cls={s.pinEnd} label={t("legendEnd")} />
                  <Legend cls={s.pinStop} label={t("legendStop")} />
                </>
              )}
            </ul>
          )}
          {lineNote && <span>{lineNote}</span>}
        </div>
      )}
    </section>
  );
}

function Legend({ cls, label }: { cls: string; label: string }) {
  return (
    <li>
      <span className={cls} aria-hidden="true" />
      {label}
    </li>
  );
}
