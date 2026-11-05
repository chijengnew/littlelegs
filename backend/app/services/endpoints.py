"""起訖點解析。

- place_ref：本專案地點，座標來自獨立來源。
- google_place：其他地點（例如家）。每次搜尋／排序／重算以 Place Details（id、location）重新解析；
  Google 座標只供當次計算，不寫入查詢 JSON、資料庫、sessionStorage 或日誌。
  會員的私人端點身分以 (user_id, Place ID／已確認 alias) 重用；不接受其他會員的私人端點 ID。
- device_coordinate：裝置座標，保存原精度；精確度只作提示。
- 位置不可用或不在台灣服務範圍時停止，不以預設座標替代。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Place, PrivateEndpoint, PrivateEndpointAlias
from app.errors import ApiError
from app.external.google import Deadline, GoogleError
from app.geo import in_taiwan
from app.ids import new_id
from app.ratelimit import QuotaExceeded
from app.services.places import reliable_place_id
from app.state import AppState


@dataclass
class ResolvedEndpoint:
    kind: str
    lat: float
    lon: float
    coord_source: str
    place_ref: str | None = None
    google_place_id: str | None = None
    private_endpoint_id: str | None = None
    label: str | None = None
    removed: bool = False
    place_name: str | None = None
    place_address: str | None = None


async def find_private_endpoint(s: AsyncSession, user_id: uuid.UUID, google_place_id: str) -> uuid.UUID | None:
    return (
        await s.execute(
            select(PrivateEndpointAlias.endpoint_id).where(
                PrivateEndpointAlias.user_id == user_id, PrivateEndpointAlias.google_place_id == google_place_id
            )
        )
    ).scalar()


async def ensure_private_endpoint(s: AsyncSession, user_id: uuid.UUID, google_place_id: str) -> uuid.UUID:
    """同一會員相同 Place ID 重用同一端點身分；須在呼叫端的寫入交易內執行。"""
    eid = await find_private_endpoint(s, user_id, google_place_id)
    if eid is not None:
        return eid
    eid = new_id()
    try:
        async with s.begin_nested():
            s.add(PrivateEndpoint(id=eid, user_id=user_id, google_place_id=google_place_id))
            await s.flush()
            s.add(PrivateEndpointAlias(user_id=user_id, google_place_id=google_place_id, endpoint_id=eid))
            await s.flush()
    except IntegrityError:
        eid2 = await find_private_endpoint(s, user_id, google_place_id)
        if eid2 is None:
            raise
        return eid2
    return eid


async def owned_endpoint_place_id(s: AsyncSession, user_id: uuid.UUID, endpoint_id: str) -> str:
    row = (
        await s.execute(
            select(PrivateEndpoint.google_place_id).where(
                PrivateEndpoint.id == uuid.UUID(endpoint_id), PrivateEndpoint.user_id == user_id
            )
        )
    ).scalar()
    if row is None:
        raise ApiError(403, "ENDPOINT_FORBIDDEN", "無法使用此私人端點")
    return row


async def resolve(st: AppState, s: AsyncSession, ep, user_id: uuid.UUID | None, deadline: Deadline) -> ResolvedEndpoint:
    if ep.type == "place_ref":
        p = (
            await s.execute(
                select(
                    Place.lat,
                    Place.lon,
                    Place.removed_at,
                    Place.name,
                    Place.address,
                    Place.google_place_id,
                    Place.place_id_status,
                ).where(Place.id == uuid.UUID(ep.place_id))
            )
        ).first()
        if p is None:
            raise ApiError(422, "ENDPOINT_NOT_FOUND", "找不到此地點，請重新選擇")
        r = ResolvedEndpoint(
            "place_ref",
            float(p.lat),
            float(p.lon),
            "open_data",
            place_ref=ep.place_id,
            google_place_id=reliable_place_id(p.google_place_id, p.place_id_status),
            removed=p.removed_at is not None,
            place_name=p.name,
            place_address=p.address,
        )
    elif ep.type == "google_place":
        gpid = ep.google_place_id
        eid = None
        if ep.endpoint_id is not None:
            if user_id is None:
                raise ApiError(422, "ENDPOINT_FORBIDDEN", "訪客不可使用私人端點參照")
            stored = await owned_endpoint_place_id(s, user_id, ep.endpoint_id)
            if stored != gpid:
                alias = await find_private_endpoint(s, user_id, gpid)
                if alias is None or str(alias) != ep.endpoint_id:
                    raise ApiError(422, "ENDPOINT_MISMATCH", "端點參照與 Place ID 不一致，請重新選擇")
            eid = ep.endpoint_id
        elif user_id is not None:
            found = await find_private_endpoint(s, user_id, gpid)
            eid = None if found is None else str(found)
        if st.google is None:
            raise ApiError(503, "EXTERNAL_UNAVAILABLE", "地點解析服務未設定")
        try:
            lat, lon = await st.google.place_location(gpid, deadline)
        except QuotaExceeded:
            raise
        except GoogleError as e:
            if e.kind == "not_found":
                raise ApiError(
                    409, "ENDPOINT_PLACE_NOT_FOUND", "此地點已無法解析，請重新選擇（無原始搜尋依據，無法自動找回）"
                ) from e
            raise ApiError(503, "ENDPOINT_RESOLVE_FAILED", "暫時無法解析起訖點") from e
        r = ResolvedEndpoint(
            "google_place", lat, lon, "google", google_place_id=gpid, private_endpoint_id=eid, label=ep.label
        )
    else:
        r = ResolvedEndpoint("device_coordinate", ep.lat, ep.lng, "device", label=ep.label)
    if not in_taiwan(r.lat, r.lon):
        raise ApiError(422, "OUT_OF_SERVICE_AREA", "起點、終點須位於台灣服務範圍")
    return r


def identity(r: ResolvedEndpoint, ep) -> str:
    from app.domain.fingerprint import endpoint_identity

    return endpoint_identity(ep, r.private_endpoint_id)
