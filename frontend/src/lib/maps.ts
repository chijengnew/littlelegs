const API_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "";
const MAP_ID = process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID ?? "";

export function isMapConfigured(): boolean {
  return Boolean(API_KEY && MAP_ID);
}

export const mapId = MAP_ID;

export type GLatLng = { lat: number; lng: number };
export type GBounds = { north: number; south: number; east: number; west: number };
export interface GMap {
  fitBounds(bounds: GBounds, padding?: number): void;
  setCenter(c: GLatLng): void;
  setZoom(z: number): void;
}
export interface GMarker {
  map: GMap | null;
}
export interface GPolyline {
  setMap(map: GMap | null): void;
}
export type MapsLib = {
  Map: new (el: HTMLElement, opts: Record<string, unknown>) => GMap;
  Polyline: new (opts: Record<string, unknown>) => GPolyline;
};
export type MarkerLib = {
  AdvancedMarkerElement: new (opts: {
    map: GMap;
    position: GLatLng;
    content?: HTMLElement;
    title?: string;
    zIndex?: number;
  }) => GMarker;
};
export type Libraries = { maps: MapsLib; marker: MarkerLib };

type GoogleGlobal = { maps: { importLibrary(name: string): Promise<unknown> } };
type MapsWindow = Window & {
  google?: GoogleGlobal;
  gm_authFailure?: () => void;
  __littlelegsMapsReady?: () => void;
};

let loading: Promise<Libraries> | undefined;
let authFailed = false;
const authListeners = new Set<() => void>();

export function onMapAuthFailure(fn: () => void): () => void {
  if (authFailed) fn();
  authListeners.add(fn);
  return () => authListeners.delete(fn);
}

export function loadMaps(): Promise<Libraries> {
  if (typeof window === "undefined" || !isMapConfigured()) return Promise.reject(new Error("MAP_NOT_CONFIGURED"));
  if (loading) return loading;
  const w = window as MapsWindow;
  loading = new Promise<void>((resolve, reject) => {
    if (w.google?.maps?.importLibrary) return resolve();
    w.gm_authFailure = () => {
      authFailed = true;
      authListeners.forEach((fn) => fn());
    };
    w.__littlelegsMapsReady = () => resolve();
    const params = new URLSearchParams({
      key: API_KEY,
      v: "weekly",
      language: "zh-TW",
      region: "TW",
      loading: "async",
      callback: "__littlelegsMapsReady",
    });
    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?${params}`;
    script.async = true;
    script.onerror = () => {
      script.remove();
      reject(new Error("MAP_LOAD_FAILED"));
    };
    document.head.append(script);
  })
    .then(async () => {
      const g = w.google!.maps;
      const [maps, marker] = await Promise.all([g.importLibrary("maps"), g.importLibrary("marker")]);
      return { maps: maps as MapsLib, marker: marker as MarkerLib };
    })
    .catch((e) => {
      loading = undefined;
      throw e;
    });
  return loading;
}
