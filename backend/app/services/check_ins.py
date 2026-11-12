"""探險護照到訪紀錄：建立、升級、查詢、刪除與任務計數。

- 同一會員、同一景點最多一筆。先手動、後定位成功時升級為 location，保留首次 visited_at，另記 verified_at；
  已是 location 的紀錄收到 manual 請求時回傳既有紀錄，不降級。
- 可蓋章：未下架的 kind=attraction，且座標來自授權已核對的獨立來源紀錄；不要求 Google Place ID，旅宿不可蓋章。
- Idempotency-Key（UUIDv7）規則同收藏：格式非法 422；key_time > now+24h → 409 KEY_TIME_INVALID；
  now ≥ key_time+7d → 409 OPERATION_EXPIRED；同 key 不同景點或方式 → 409 IDEMPOTENCY_CONFLICT；
  紀錄已刪除的舊 key → 409 OPERATION_CANCELLED。定位核對未通過時整筆回滾，不留下可重播的結果。
- 到訪紀錄與操作紀錄在同一 MySQL 交易提交；併發以唯一限制與列鎖序列化，衝突時重試並回傳既有結果。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Stamping
from app.db.base import rowcount
from app.db.models import CheckIn, CheckInOperation, Dataset, Place, SourceRecord
from app.domain.missions import CountedPlace
from app.domain.stamping import FINGERPRINT_VERSION, CheckInIn, check_location, request_fingerprint
from app.domain.validation import check_key_time, favorite_key_expiry
from app.errors import ApiError
from app.ids import new_id
from app.services.history import encode_cursor, keyset
from app.services.users import lock_active_user


@dataclass(frozen=True)
class PlaceSummary:
    place_id: uuid.UUID
    name: str
    primary_type: str | None
    city: str | None
    removed: bool


@dataclass(frozen=True)
class CheckInView:
    check_in: CheckIn
    place: PlaceSummary


@dataclass(frozen=True)
class CreateResult:
    view: CheckInView
    outcome: str


def _place_columns():
    lic = (
        select(Dataset.license_status)
        .join(SourceRecord, SourceRecord.dataset_id == Dataset.id)
        .where(SourceRecord.id == Place.coord_source_record_id)
        .scalar_subquery()
        .label("license_status")
    )
    return (
        Place.id,
        Place.kind,
        Place.name,
        Place.primary_type,
        Place.city,
        Place.lat,
        Place.lon,
        Place.removed_at,
        Place.coord_source_record_id,
        lic,
    )


def _summary(r) -> PlaceSummary:
    return PlaceSummary(r.id, r.name, r.primary_type, r.city, r.removed_at is not None)


async def create(
    factory, user_id: uuid.UUID, key: uuid.UUID, body: CheckInIn, now: datetime, rules: Stamping
) -> CreateResult:
    check_key_time(key, now)
    if now >= favorite_key_expiry(key):
        raise ApiError(409, "OPERATION_EXPIRED", "此操作識別碼已過期，請重新操作")
    for attempt in range(3):
        try:
            return await _create_tx(factory, user_id, key, body, now, rules)
        except IntegrityError:
            if attempt == 2:
                raise
        except OperationalError as e:
            errno = getattr(getattr(e, "orig", None), "args", (None,))[0]
            if errno not in (1213, 1205) or attempt == 2:
                raise
    raise RuntimeError("unreachable")


async def _replay(s: AsyncSession, user_id: uuid.UUID, op: CheckInOperation, req_fp: bytes, now: datetime):
    if now >= op.expires_at:
        raise ApiError(409, "OPERATION_EXPIRED", "此操作識別碼已過期，請重新操作")
    if op.request_fingerprint != req_fp:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "同一操作識別碼的內容不同")
    if op.state == "cancelled":
        raise ApiError(409, "OPERATION_CANCELLED", "這筆到訪紀錄已刪除；若要再蓋章請重新操作")
    row = (
        await s.execute(
            select(CheckIn, *_place_columns())
            .join(Place, Place.id == CheckIn.place_id)
            .where(CheckIn.id == op.check_in_id, CheckIn.user_id == user_id)
        )
    ).first()
    if row is None:
        raise ApiError(409, "OPERATION_CANCELLED", "這筆到訪紀錄已不存在；若要再蓋章請重新操作")
    return CreateResult(CheckInView(row.CheckIn, _summary(row)), op.outcome)


async def _create_tx(
    factory, user_id: uuid.UUID, key: uuid.UUID, body: CheckInIn, now: datetime, rules: Stamping
) -> CreateResult:
    req_fp = request_fingerprint(body.place_id, body.verification_method)
    async with factory() as s, s.begin():
        await lock_active_user(s, user_id)
        op = (
            await s.execute(
                select(CheckInOperation)
                .where(CheckInOperation.user_id == user_id, CheckInOperation.idempotency_key == key)
                .with_for_update()
            )
        ).scalar()
        if op is not None:
            return await _replay(s, user_id, op, req_fp, now)

        pid = uuid.UUID(body.place_id)
        p = (await s.execute(select(*_place_columns()).where(Place.id == pid))).first()
        if p is None:
            raise ApiError(404, "PLACE_NOT_FOUND", "找不到此地點")
        if p.kind != "attraction":
            raise ApiError(422, "PLACE_NOT_STAMPABLE", "只有景點可以蓋章，旅宿不能蓋章")
        if p.removed_at is not None:
            raise ApiError(409, "PLACE_REMOVED", "這個景點已下架，不能新增到訪紀錄")
        if p.coord_source_record_id is None or p.license_status != "verified":
            raise ApiError(422, "PLACE_NO_COORDINATES", "這個景點沒有可用的參考位置，暫時不能蓋章")

        ci = (
            await s.execute(
                select(CheckIn).where(CheckIn.user_id == user_id, CheckIn.place_id == pid).with_for_update()
            )
        ).scalar()
        method = body.verification_method
        if ci is not None and (ci.verification_method == "location" or method == "manual"):
            outcome = "existing"
        else:
            if method == "location":
                assert body.location is not None
                check_location(float(p.lat), float(p.lon), body.location, rules)
            if ci is None:
                ci = CheckIn(
                    id=new_id(),
                    user_id=user_id,
                    place_id=pid,
                    verification_method=method,
                    visited_at=now,
                    verified_at=now if method == "location" else None,
                    created_at=now,
                    updated_at=now,
                )
                s.add(ci)
                outcome = "created"
            else:
                ci.verification_method = "location"
                ci.verified_at = now
                ci.updated_at = now
                outcome = "upgraded"
            await s.flush()
        s.add(
            CheckInOperation(
                user_id=user_id,
                idempotency_key=key,
                request_fingerprint=req_fp,
                fingerprint_version=FINGERPRINT_VERSION,
                state="completed",
                outcome=outcome,
                check_in_id=ci.id,
                expires_at=favorite_key_expiry(key),
                created_at=now,
            )
        )
        await s.flush()
        return CreateResult(CheckInView(ci, _summary(p)), outcome)


async def list_check_ins(
    factory, user_id: uuid.UUID, cursor: str | None, limit: int, place_id: uuid.UUID | None
) -> tuple[list[CheckInView], str | None]:
    async with factory() as s:
        q = (
            select(CheckIn, *_place_columns())
            .join(Place, Place.id == CheckIn.place_id)
            .where(CheckIn.user_id == user_id)
        )
        if place_id is not None:
            q = q.where(CheckIn.place_id == place_id)
        k = keyset(CheckIn, cursor)
        if k is not None:
            q = q.where(k)
        rows = (await s.execute(q.order_by(CheckIn.created_at.desc(), CheckIn.id.desc()).limit(limit + 1))).all()
    views = [CheckInView(r.CheckIn, _summary(r)) for r in rows]
    last = views[limit - 1].check_in if len(views) > limit else None
    nxt = encode_cursor(last.created_at, last.id) if last is not None else None
    return views[:limit], nxt


async def counts(factory, user_id: uuid.UUID) -> dict[str, int]:
    async with factory() as s:
        rows = (
            await s.execute(
                select(CheckIn.verification_method, func.count())
                .where(CheckIn.user_id == user_id)
                .group_by(CheckIn.verification_method)
            )
        ).all()
    by = {m: int(n) for m, n in rows}
    return {"total": sum(by.values()), "location": by.get("location", 0), "manual": by.get("manual", 0)}


async def mission_places(factory, user_id: uuid.UUID) -> list[CountedPlace]:
    async with factory() as s:
        rows = (
            await s.execute(
                select(Place.id, Place.primary_type)
                .join(CheckIn, CheckIn.place_id == Place.id)
                .where(
                    CheckIn.user_id == user_id,
                    CheckIn.verification_method == "location",
                    Place.kind == "attraction",
                    Place.removed_at.is_(None),
                )
            )
        ).all()
    return [CountedPlace(str(r.id), r.primary_type) for r in rows]


async def delete_check_in_rows(s: AsyncSession, user_id: uuid.UUID, cid: uuid.UUID) -> int:
    """刪除單筆到訪紀錄，並讓指向它的建立操作永久失效（延遲重送不會讓紀錄復活）。"""
    await s.execute(
        update(CheckInOperation)
        .where(CheckInOperation.user_id == user_id, CheckInOperation.check_in_id == cid)
        .values(state="cancelled")
    )
    r = await s.execute(delete(CheckIn).where(CheckIn.id == cid, CheckIn.user_id == user_id))
    return rowcount(r)
