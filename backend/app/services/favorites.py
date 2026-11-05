"""收藏：內容身分與冪等操作。

- 收藏內容不可編輯、不可命名，只能刪除或另存；不因儲存另查付費 API，也不信任客戶端自報的可行性。
- 內容身分＝完整標準化條件＋起訖身分＋有序景點內部 ID＋各點停留時間；(user_id, content_fingerprint) 唯一。
- Idempotency-Key（UUIDv7）：格式非法 422；key_time > now+24h → 409 KEY_TIME_INVALID；
  now ≥ key_time+7d → 409 OPERATION_EXPIRED（先期限檢查再去重）；同 key 不同內容 → 409 IDEMPOTENCY_CONFLICT；
  已取消的舊 key → 409 OPERATION_CANCELLED。
- 收藏與操作紀錄在同一 MySQL 交易提交；併發以唯一限制與列鎖序列化，唯一限制衝突改回既有結果，不回 500。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Favorite, FavoriteOperation, FavoriteStop, History
from app.domain import ranking
from app.domain.fingerprint import FINGERPRINT_VERSION, favorite_content_fingerprint, favorite_request_fingerprint
from app.domain.schemas import FavoriteIn
from app.domain.validation import check_key_time, favorite_key_expiry
from app.errors import ApiError
from app.geo import haversine_m
from app.ids import new_id
from app.services.endpoints import owned_endpoint_place_id
from app.services.history import _labels, member_endpoint_ids
from app.services.places import load_places
from app.services.users import lock_active_user

SAVED_NOTICE = "已保存計畫，未於儲存時重新驗證"


@dataclass
class FavoriteResult:
    favorite: Favorite
    created: bool


async def _check_endpoint_refs(s: AsyncSession, user_id: uuid.UUID, body: FavoriteIn) -> None:
    for ep in (body.conditions.start, body.conditions.end):
        if ep is not None and ep.type == "google_place" and ep.endpoint_id is not None:
            stored = await owned_endpoint_place_id(s, user_id, ep.endpoint_id)
            if stored != ep.google_place_id:
                raise ApiError(422, "ENDPOINT_MISMATCH", "端點參照與 Place ID 不一致")


def _start_coord(body: FavoriteIn, places: dict) -> tuple[float, float, str] | None:
    """nearby 原因只在起點座標不是 Google 時計算。"""
    ep = body.conditions.start
    if ep.type == "device_coordinate":
        return ep.lat, ep.lng, "device"
    if ep.type == "place_ref":
        p = places.get(uuid.UUID(ep.place_id))
        if p is not None:
            return p.lat, p.lon, "open_data"
    return None


async def create(factory, user_id: uuid.UUID, key: uuid.UUID, body: FavoriteIn, now: datetime) -> FavoriteResult:
    check_key_time(key, now)
    if now >= favorite_key_expiry(key):
        raise ApiError(409, "OPERATION_EXPIRED", "此操作識別碼已過期，請重新操作")
    for attempt in range(3):
        try:
            return await _create_tx(factory, user_id, key, body, now)
        except IntegrityError:
            if attempt == 2:
                raise
        except OperationalError as e:
            errno = getattr(getattr(e, "orig", None), "args", (None,))[0]
            if errno not in (1213, 1205) or attempt == 2:
                raise
    raise RuntimeError("unreachable")


async def _create_tx(factory, user_id: uuid.UUID, key: uuid.UUID, body: FavoriteIn, now: datetime) -> FavoriteResult:
    c = body.conditions
    async with factory() as s, s.begin():
        await lock_active_user(s, user_id)
        await _check_endpoint_refs(s, user_id, body)
        place_ids = [uuid.UUID(x.place_id) for x in body.stops]
        places = await load_places(s, place_ids)
        stops: list[tuple] = []
        for i, x in enumerate(body.stops):
            p = places.get(uuid.UUID(x.place_id))
            if p is None or p.kind != "attraction":
                raise ApiError(422, "STOP_NOT_FOUND", "找不到選取的景點", errors=[{"loc": ["stops", str(i)]}])
            stay, src = ranking.default_stay(p, x.stay_minutes)
            stops.append((p, stay, src))
        if body.source_history_id is not None:
            ok = (
                await s.execute(
                    select(History.id).where(
                        History.id == uuid.UUID(body.source_history_id), History.user_id == user_id
                    )
                )
            ).scalar()
            if ok is None:
                raise ApiError(422, "HISTORY_NOT_FOUND", "來源歷史不存在")

        sid, eid, stored = await member_endpoint_ids(s, user_id, c)
        content_fp = favorite_content_fingerprint(c, sid, eid, [(p.ref, stay) for p, stay, _ in stops])
        req_fp = favorite_request_fingerprint(content_fp, body.saved_as)

        op = (
            await s.execute(
                select(FavoriteOperation)
                .where(FavoriteOperation.user_id == user_id, FavoriteOperation.idempotency_key == key)
                .with_for_update()
            )
        ).scalar()
        if op is not None:
            if now >= op.expires_at:
                raise ApiError(409, "OPERATION_EXPIRED", "此操作識別碼已過期，請重新操作")
            if op.request_fingerprint != req_fp:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "同一操作識別碼的內容不同")
            if op.state == "cancelled":
                raise ApiError(409, "OPERATION_CANCELLED", "此收藏已取消；若要再收藏請重新操作")
            fav = await s.get(Favorite, op.favorite_id) if op.favorite_id else None
            if fav is None:
                raise ApiError(409, "OPERATION_CANCELLED", "此收藏已不存在；若要再收藏請重新操作")
            return FavoriteResult(fav, False)

        fav = (
            await s.execute(
                select(Favorite)
                .where(Favorite.user_id == user_id, Favorite.content_fingerprint == content_fp)
                .with_for_update()
            )
        ).scalar()
        created = fav is None
        if fav is None:
            start = _start_coord(body, places)
            reasons: dict[str, list[str]] = {}
            for p, _, _ in stops:
                d = haversine_m(start[0], start[1], p.lat, p.lon) if start else float("inf")
                ev = ranking.evaluate(p, d, c.children_ages, c.facility_prefs, c.type_prefs)
                r, _ = ranking.reasons_and_warnings(ev, weather_status="not_requested", rain_checked=False)
                reasons[p.ref] = ranking.persistable_reasons(r, start[2] if start else "google")
            sl, el = _labels(c)
            fav = Favorite(
                id=new_id(),
                user_id=user_id,
                content_fingerprint=content_fp,
                fingerprint_version=FINGERPRINT_VERSION,
                source_history_id=uuid.UUID(body.source_history_id) if body.source_history_id else None,
                schema_version=c.schema_version,
                conditions=stored,
                start_label=sl,
                end_label=el,
                saved_as=body.saved_as,
                reasons={"v": 1, "stops": reasons},
                created_at=now,
            )
            s.add(fav)
            await s.flush()
            for i, (p, stay, src) in enumerate(stops):
                s.add(
                    FavoriteStop(
                        favorite_id=fav.id,
                        order_index=i,
                        place_id=p.id,
                        stay_minutes=stay,
                        stay_source=src,
                        day_index=0,
                        selected_google_place_id=p.google_place_id,
                    )
                )
        s.add(
            FavoriteOperation(
                user_id=user_id,
                idempotency_key=key,
                op_type="create",
                request_fingerprint=req_fp,
                fingerprint_version=FINGERPRINT_VERSION,
                state="completed",
                favorite_id=fav.id,
                expires_at=favorite_key_expiry(key),
                created_at=now,
            )
        )
        await s.flush()
        return FavoriteResult(fav, created)


async def list_favorites(factory, user_id: uuid.UUID, cursor: str | None, limit: int):
    from app.services.history import encode_cursor, keyset

    async with factory() as s:
        q = select(Favorite).where(Favorite.user_id == user_id)
        k = keyset(Favorite, cursor)
        if k is not None:
            q = q.where(k)
        rows = list(
            (await s.execute(q.order_by(Favorite.created_at.desc(), Favorite.id.desc()).limit(limit + 1))).scalars()
        )
    nxt = encode_cursor(rows[limit - 1].created_at, rows[limit - 1].id) if len(rows) > limit else None
    return rows[:limit], nxt


async def get_favorite(factory, user_id: uuid.UUID, fid: uuid.UUID) -> tuple[Favorite, list[FavoriteStop]]:
    async with factory() as s:
        f = (await s.execute(select(Favorite).where(Favorite.id == fid, Favorite.user_id == user_id))).scalar()
        if f is None:
            raise ApiError(404, "FAVORITE_NOT_FOUND", "找不到此收藏")
        stops = list(
            (
                await s.execute(
                    select(FavoriteStop).where(FavoriteStop.favorite_id == fid).order_by(FavoriteStop.order_index)
                )
            ).scalars()
        )
        return f, stops
