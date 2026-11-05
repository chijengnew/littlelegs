"""地點資料存取：只讀獨立來源欄位與自有屬性；不呼叫 Google。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Dataset,
    Place,
    PlaceAgeRange,
    PlaceAgeRestriction,
    PlaceFacility,
    PlaceType,
    SourceRecord,
)
from app.geo import bounding_box, haversine_m


def reliable_place_id(google_place_id: str | None, status: str) -> str | None:
    """只有查核接受的 Place ID 才給導航；待審或未配對的可能指到別的地點。"""
    return google_place_id if status == "accepted" else None


@dataclass
class PlaceData:
    id: uuid.UUID
    kind: str
    name: str
    address: str | None
    city: str | None
    lat: float
    lon: float
    google_place_id: str | None
    place_id_status: str
    primary_type: str | None
    indoor: str | None
    indoor_confirmation: str
    source_stay_minutes: int | None
    service_status: int | None
    public_access: bool | None
    removed: bool
    license_verified: bool
    types: dict[str, str] = field(default_factory=dict)
    facilities: dict[str, tuple[str, str]] = field(default_factory=dict)
    age_ranges: list[tuple[int, int, str]] = field(default_factory=list)
    age_exclusions: list[tuple[int, int]] = field(default_factory=list)

    @property
    def ref(self) -> str:
        return str(self.id)

    @property
    def navigation_place_id(self) -> str | None:
        return reliable_place_id(self.google_place_id, self.place_id_status)

    @property
    def candidate_eligible(self) -> bool:
        """可追溯、已有可用 Place ID、獨立來源座標、授權已核對、未下架、非停業／暫停、對外開放。"""
        return (
            self.kind == "attraction"
            and not self.removed
            and self.google_place_id is not None
            and self.place_id_status == "accepted"
            and self.license_verified
            and self.service_status not in (0, 3)
            and self.public_access is not False
        )


def _eligible_clause():
    lic = (
        select(Dataset.license_status)
        .join(SourceRecord, SourceRecord.dataset_id == Dataset.id)
        .where(SourceRecord.id == Place.coord_source_record_id)
        .scalar_subquery()
    )
    return and_(
        Place.kind == "attraction",
        Place.removed_at.is_(None),
        Place.google_place_id.is_not(None),
        Place.place_id_status == "accepted",
        lic == "verified",
        or_(Place.service_status.is_(None), Place.service_status.not_in([0, 3])),
        or_(Place.public_access.is_(None), Place.public_access.is_(True)),
    )


async def _attach(s: AsyncSession, places: dict[uuid.UUID, PlaceData]) -> None:
    ids = list(places)
    if not ids:
        return
    for r1 in (
        await s.execute(
            select(PlaceType.place_id, PlaceType.type, PlaceType.confirmation).where(PlaceType.place_id.in_(ids))
        )
    ).all():
        places[r1.place_id].types[r1.type] = r1.confirmation
    for r2 in (
        await s.execute(
            select(
                PlaceFacility.place_id, PlaceFacility.facility, PlaceFacility.status, PlaceFacility.confirmation
            ).where(PlaceFacility.place_id.in_(ids))
        )
    ).all():
        places[r2.place_id].facilities[r2.facility] = (r2.status, r2.confirmation)
    for r3 in (
        await s.execute(
            select(
                PlaceAgeRange.place_id, PlaceAgeRange.min_age, PlaceAgeRange.max_age, PlaceAgeRange.confirmation
            ).where(PlaceAgeRange.place_id.in_(ids))
        )
    ).all():
        places[r3.place_id].age_ranges.append((r3.min_age, r3.max_age, r3.confirmation))
    for r4 in (
        await s.execute(
            select(PlaceAgeRestriction.place_id, PlaceAgeRestriction.min_age, PlaceAgeRestriction.max_age).where(
                PlaceAgeRestriction.place_id.in_(ids)
            )
        )
    ).all():
        places[r4.place_id].age_exclusions.append((r4.min_age, r4.max_age))


def _row_to_data(r, license_verified: bool) -> PlaceData:
    return PlaceData(
        r.id,
        r.kind,
        r.name,
        r.address,
        r.city,
        float(r.lat),
        float(r.lon),
        r.google_place_id,
        r.place_id_status,
        r.primary_type,
        r.indoor,
        r.indoor_confirmation,
        r.source_stay_minutes,
        r.service_status,
        r.public_access,
        r.removed_at is not None,
        license_verified,
    )


def _base_select():
    lic = (
        select(Dataset.license_status)
        .join(SourceRecord, SourceRecord.dataset_id == Dataset.id)
        .where(SourceRecord.id == Place.coord_source_record_id)
        .scalar_subquery()
        .label("license_status")
    )
    return select(Place, lic)


async def load_places(s: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, PlaceData]:
    if not ids:
        return {}
    rows = (await s.execute(_base_select().where(Place.id.in_(ids)))).all()
    out = {r.Place.id: _row_to_data(r.Place, r.license_status == "verified") for r in rows}
    await _attach(s, out)
    return out


async def candidates_within(
    s: AsyncSession, lat: float, lon: float, radius_m: float = 30_000
) -> list[tuple[PlaceData, float]]:
    """先以經緯度 bounding box 查詢（索引 ix_places_geo），再算球面直線距離 ≤ radius（不是開車距離）。"""
    la0, la1, lo0, lo1 = bounding_box(lat, lon, radius_m)
    q = _base_select().where(_eligible_clause(), Place.lat.between(la0, la1), Place.lon.between(lo0, lo1))
    rows = (await s.execute(q)).all()
    out: dict[uuid.UUID, PlaceData] = {}
    dist: dict[uuid.UUID, float] = {}
    for r in rows:
        p = _row_to_data(r.Place, True)
        d = haversine_m(lat, lon, p.lat, p.lon)
        if d <= radius_m:
            out[p.id], dist[p.id] = p, d
    await _attach(s, out)
    return [(out[i], dist[i]) for i in out]


async def lodging_near(
    s: AsyncSession, lat: float, lon: float, radius_m: float = 10_000
) -> list[tuple[PlaceData, float]]:
    la0, la1, lo0, lo1 = bounding_box(lat, lon, radius_m)
    q = _base_select().where(
        Place.kind == "lodging", Place.removed_at.is_(None), Place.lat.between(la0, la1), Place.lon.between(lo0, lo1)
    )
    rows = (await s.execute(q)).all()
    out: dict[uuid.UUID, PlaceData] = {}
    dist: dict[uuid.UUID, float] = {}
    for r in rows:
        p = _row_to_data(r.Place, r.license_status == "verified")
        d = haversine_m(lat, lon, p.lat, p.lon)
        if d <= radius_m:
            out[p.id], dist[p.id] = p, d
    await _attach(s, out)
    return [(out[i], dist[i]) for i in out]


async def search_by_name(s: AsyncSession, q: str, kind: str | None, limit: int) -> list[PlaceData]:
    """起訖點選取：只查本專案未下架地點，不呼叫 Google。"""
    like = "%" + q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
    cond: list[ColumnElement[bool]] = [Place.removed_at.is_(None), Place.name.like(like)]
    if kind:
        cond.append(Place.kind == kind)
    rows = (
        await s.execute(_base_select().where(*cond).order_by(func.char_length(Place.name), Place.id).limit(limit))
    ).all()
    return [_row_to_data(r.Place, r.license_status == "verified") for r in rows]


async def place_detail(s: AsyncSession, pid: uuid.UUID) -> dict | None:
    data = (await load_places(s, [pid])).get(pid)
    if data is None:
        return None
    srcs = (
        await s.execute(
            select(SourceRecord, Dataset)
            .join(Dataset, Dataset.id == SourceRecord.dataset_id)
            .where(SourceRecord.place_id == pid)
        )
    ).all()
    pl = await s.get(Place, pid)
    evidence: dict[str, Any] = {
        "types": [],
        "facilities": [],
        "indoor": None
        if pl is None
        else {
            "value": pl.indoor,
            "confirmation": pl.indoor_confirmation,
            "source_type": pl.indoor_source_type,
            "evidence": pl.indoor_evidence_note,
            "evidence_record_id": _s(pl.indoor_evidence_record_id),
            "verified_at": _iso(pl.indoor_verified_at),
        },
        "age_ranges": [],
        "age_exclusions": [],
    }
    for pt in (await s.execute(select(PlaceType).where(PlaceType.place_id == pid))).scalars():
        evidence["types"].append(
            {
                "type": pt.type,
                "confirmation": pt.confirmation,
                "source_type": pt.source_type,
                "evidence": pt.evidence_note,
                "evidence_record_id": _s(pt.evidence_record_id),
                "verified_at": _iso(pt.verified_at),
            }
        )
    for pf in (await s.execute(select(PlaceFacility).where(PlaceFacility.place_id == pid))).scalars():
        evidence["facilities"].append(
            {
                "facility": pf.facility,
                "status": pf.status,
                "confirmation": pf.confirmation,
                "source_type": pf.source_type,
                "evidence": pf.evidence_note,
                "evidence_record_id": _s(pf.evidence_record_id),
                "verified_at": _iso(pf.verified_at),
            }
        )
    for pa in (await s.execute(select(PlaceAgeRange).where(PlaceAgeRange.place_id == pid))).scalars():
        evidence["age_ranges"].append(
            {
                "min_age": pa.min_age,
                "max_age": pa.max_age,
                "confirmation": pa.confirmation,
                "source_type": pa.source_type,
                "evidence": pa.evidence_note,
                "evidence_record_id": _s(pa.evidence_record_id),
                "verified_at": _iso(pa.verified_at),
            }
        )
    for px in (await s.execute(select(PlaceAgeRestriction).where(PlaceAgeRestriction.place_id == pid))).scalars():
        evidence["age_exclusions"].append(
            {
                "min_age": px.min_age,
                "max_age": px.max_age,
                "source_type": px.source_type,
                "evidence": px.evidence_note,
                "evidence_record_id": _s(px.evidence_record_id),
                "verified_at": _iso(px.verified_at),
            }
        )
    return {
        "place": data,
        "sources": [
            {
                "source_record_id": str(sr.id),
                "dataset_key": ds.dataset_key,
                "dataset_title": ds.title,
                "provider": ds.provider,
                "source_url": ds.source_url,
                "license": ds.license,
                "license_status": ds.license_status,
                "dataset_updated_at": iso_text(ds.source_updated_at),
                "record_updated_at": iso_text(sr.source_updated_at),
                "removed": sr.removed_at is not None,
                "name": sr.name,
                "address": sr.address,
                "display": sr.display,
            }
            for sr, ds in srcs
        ],
        "evidence": evidence,
    }


def _s(u) -> str | None:
    return None if u is None else str(u)


def _iso(d) -> str | None:
    return None if d is None else d.isoformat()


_SOURCE_TS = re.compile(
    r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})"
    r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?"
    r"\s*(Z|[+-]\d{2}:?\d{2})?$"
)


def iso_text(v: str | None) -> str | None:
    """來源時間字串在資料庫原樣保存；輸出時統一為 ISO 8601，無法辨識則原樣回傳。

    來源沒有標示時區就不補時區；只有日期就只回日期。
    """
    if v is None:
        return None
    m = _SOURCE_TS.match(v.strip())
    if m is None:
        return v
    y, mo, d, h, mi, sec, tz = m.groups()
    try:
        if h is None:
            return date(int(y), int(mo), int(d)).isoformat()
        out = datetime(int(y), int(mo), int(d), int(h), int(mi), int(sec or 0)).isoformat()
    except ValueError:
        return v
    if tz:
        out += "+00:00" if tz == "Z" else f"{tz[:3]}:{tz[-2:]}"
    return out
