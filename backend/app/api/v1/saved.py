"""歷史／收藏的共用輸出與重新檢查。

開啟時分區顯示「收藏當時的推薦原因」（只含獨立來源／使用者輸入成立的原因）與「本次檢查」（另行重算）；
原因不得呈現成現況保證；地點下架或來源變更顯示原因，不偷換景點或覆寫原快照。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import Place
from app.domain.ranking import REASON_TEMPLATES_ZH
from app.domain.schemas import Conditions, StopIn
from app.errors import ApiError
from app.services import planning
from app.services.places import load_places
from app.services.users import CurrentUser
from app.state import AppState


def _reasons(reasons: dict | None, place_id: str) -> list[dict]:
    codes = ((reasons or {}).get("stops") or {}).get(place_id) or []
    msgs = {**REASON_TEMPLATES_ZH, "facility_match": "收藏當時有符合的設施資料"}
    return [{"code": c, "message": msgs.get(c, c)} for c in codes]


async def stops_out(st: AppState, stops, reasons: dict | None) -> list[dict]:
    async with st.factory() as s:
        places = await load_places(s, [x.place_id for x in stops])
    out = []
    for x in stops:
        p = places.get(x.place_id)
        out.append(
            {
                "order_index": x.order_index,
                "place_id": str(x.place_id),
                "name": p.name if p else None,
                "address": p.address if p else None,
                "google_place_id": p.navigation_place_id if p else None,
                "primary_type": p.primary_type if p else None,
                "stay_minutes": x.stay_minutes,
                "stay_source": x.stay_source,
                "removed": p is None or p.removed,
                "reasons_at_save": _reasons(reasons, str(x.place_id)),
                "location": None if p is None else {"lat": p.lat, "lng": p.lon, "source": "open_data"},
            }
        )
    return out


def _place_ref_id(ep: object) -> str | None:
    if isinstance(ep, dict) and ep.get("type") == "place_ref" and isinstance(ep.get("place_id"), str):
        return ep["place_id"]
    return None


async def place_names(st: AppState, conditions_list: list[dict]) -> dict[str, str]:
    """起訖點為本專案地點（place_ref）時的開放資料名稱；列表一次查完，不呼叫 Google。"""
    ids: set[uuid.UUID] = set()
    for c in conditions_list:
        for k in ("start", "end"):
            pid = _place_ref_id((c or {}).get(k))
            if pid:
                try:
                    ids.add(uuid.UUID(pid))
                except ValueError:
                    continue
    if not ids:
        return {}
    async with st.factory() as s:
        rows = (await s.execute(select(Place.id, Place.name).where(Place.id.in_(ids)))).all()
    return {str(r.id): r.name for r in rows}


def endpoint_place_names(conditions: dict, names: dict[str, str]) -> tuple[str | None, str | None]:
    """回傳（起點名稱, 終點名稱）；終點同起點（end 為 null）時沿用起點。非 place_ref 為 None。"""
    c = conditions or {}

    def one(ep: object) -> str | None:
        pid = _place_ref_id(ep)
        return names.get(pid) if pid else None

    start = one(c.get("start"))
    return start, start if c.get("end") is None else one(c.get("end"))


async def endpoint_locations(st: AppState, conditions: dict) -> tuple[dict | None, dict | None]:
    """詳細頁地圖用的起訖點座標（起點, 終點）；終點同起點（end 為 null）時沿用起點。

    本專案地點用開放資料座標，裝置座標用保存的條件；Google 地點的座標不可保存，回傳 None（按重新檢查才取得）。
    """
    c = conditions or {}
    ids: dict[str, uuid.UUID] = {}
    for k in ("start", "end"):
        pid = _place_ref_id(c.get(k))
        if pid:
            try:
                ids[k] = uuid.UUID(pid)
            except ValueError:
                continue
    coords: dict[uuid.UUID, tuple[float, float]] = {}
    if ids:
        async with st.factory() as s:
            q = select(Place.id, Place.lat, Place.lon).where(Place.id.in_(set(ids.values())))
            rows = (await s.execute(q)).all()
        coords = {r.id: (float(r.lat), float(r.lon)) for r in rows}

    def one(k: str) -> dict | None:
        ep = c.get(k)
        if k in ids and ids[k] in coords:
            lat, lng = coords[ids[k]]
            return {"lat": lat, "lng": lng, "source": "open_data"}
        if isinstance(ep, dict) and ep.get("type") == "device_coordinate":
            dlat, dlng = ep.get("lat"), ep.get("lng")
            if isinstance(dlat, (int, float)) and isinstance(dlng, (int, float)):
                return {"lat": float(dlat), "lng": float(dlng), "source": "device"}
        return None

    start = one("start")
    return start, start if c.get("end") is None else one("end")


async def endpoint_navigation(
    st: AppState, conditions: dict, start_label: str | None, end_label: str | None
) -> tuple[dict | None, dict | None]:
    """詳細頁導航用的起訖點（起點, 終點）；終點同起點（end 為 null）時沿用起點。開啟時不呼叫 Google。"""
    c = conditions or {}
    ids: set[uuid.UUID] = set()
    for k in ("start", "end"):
        pid = _place_ref_id(c.get(k))
        if pid:
            try:
                ids.add(uuid.UUID(pid))
            except ValueError:
                continue
    async with st.factory() as s:
        places = await load_places(s, list(ids))

    def one(ep: object, label: str | None) -> dict | None:
        if not isinstance(ep, dict):
            return None
        kind = ep.get("type")
        if kind == "place_ref":
            try:
                p = places.get(uuid.UUID(str(ep.get("place_id"))))
            except ValueError:
                return None
            if p is None:
                return None
            return {
                "type": kind,
                "place_id": p.ref,
                "removed": p.removed,
                "name": p.name,
                "address": p.address,
                "google_place_id": p.navigation_place_id,
            }
        if kind == "google_place" and isinstance(ep.get("google_place_id"), str):
            return {"type": kind, "google_place_id": ep["google_place_id"], "label": label}
        if kind == "device_coordinate":
            lat, lng = ep.get("lat"), ep.get("lng")
            if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                return {"type": kind, "coordinate": {"lat": float(lat), "lng": float(lng)}}
        return None

    start = one(c.get("start"), start_label)
    return start, start if c.get("end") is None else one(c.get("end"), end_label)


def stored_conditions(raw: dict) -> Conditions:
    try:
        return Conditions.model_validate(raw)
    except Exception as e:
        raise ApiError(409, "SAVED_CONDITIONS_UNREADABLE", "保存的條件格式無法讀取，請重新規劃") from e


async def recheck(st: AppState, user: CurrentUser, label: str, conditions: dict, stops) -> dict:
    c = stored_conditions(conditions)
    if not stops:
        return {"rechecked": False, "reason": "NO_STOPS", "message": "此紀錄尚未選擇景點"}
    sin = [StopIn(place_id=str(x.place_id), stay_minutes=x.stay_minutes) for x in stops]
    res = await planning.recheck_saved(st, user, label, c, sin, [x.stay_source for x in stops])
    if not res.get("rechecked"):
        return res
    checked_at = res.pop("checked_at")
    res.pop("rechecked")
    return {"rechecked": True, "checked_at": checked_at, "plan": res}


def parse_path_id(v: str, code: str) -> uuid.UUID:
    from app.ids import parse_uuid7

    try:
        return parse_uuid7(v)
    except ValueError as e:
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "識別碼必須是小寫標準 UUIDv7",
            errors=[{"loc": ["path", code], "msg": "invalid uuid7"}],
        ) from e
