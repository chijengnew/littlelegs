"""使用者回饋的保存、過期清理與維運匯出。

回饋不主動關聯會員帳號，但內容與信箱仍可能含可識別個人的資料：
- 當事人可透過聯絡信箱申請查詢或刪除（scripts/feedback.py 依信箱查詢、依編號刪除）。
- 保存期限 RETENTION，由 scripts/maintenance.py 清除；排程未安裝時不會自動刪除。
"""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.base import rowcount
from app.db.models import Feedback, Place
from app.domain.schemas import FeedbackIn
from app.errors import ApiError
from app.ids import new_id
from app.timeutil import local_dt

RETENTION = timedelta(days=365)
CSV_COLUMNS = ("id", "created_at", "type", "rating", "source_page", "place_id", "contact_email", "content")


async def create(factory: async_sessionmaker[AsyncSession], body: FeedbackIn, now: datetime) -> uuid.UUID:
    place_id = None if body.place_id is None else uuid.UUID(body.place_id)
    async with factory() as s, s.begin():
        if place_id is not None and (await s.execute(select(Place.id).where(Place.id == place_id))).first() is None:
            raise ApiError(422, "PLACE_NOT_FOUND", "找不到回報的景點")
        row = Feedback(
            id=new_id(),
            type=body.type,
            rating=body.rating,
            content=body.content,
            contact_email=body.contact_email,
            source_page=body.source_page,
            place_id=place_id,
            created_at=now,
        )
        s.add(row)
    return row.id


async def purge_expired(factory: async_sessionmaker[AsyncSession], now: datetime) -> int:
    """刪除建立已超過保存期限的回饋，回傳筆數。"""
    async with factory() as s, s.begin():
        return rowcount(await s.execute(delete(Feedback).where(Feedback.created_at < now - RETENTION)))


async def find(
    factory: async_sessionmaker[AsyncSession], *, since: date | None = None, email: str | None = None
) -> list[Feedback]:
    q = select(Feedback).order_by(Feedback.created_at)
    if since is not None:
        q = q.where(Feedback.created_at >= local_dt(since, datetime.min.time()))
    if email is not None:
        q = q.where(Feedback.contact_email == email)
    async with factory() as s:
        return list((await s.execute(q)).scalars())


async def delete_one(factory: async_sessionmaker[AsyncSession], feedback_id: uuid.UUID) -> bool:
    async with factory() as s, s.begin():
        return rowcount(await s.execute(delete(Feedback).where(Feedback.id == feedback_id))) > 0


def _cell(value: object) -> str:
    """內容來自使用者：開頭是公式字元時加上單引號，避免在試算表中被當成公式執行。"""
    text = "" if value is None else str(value)
    return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def rows_to_csv(rows: Iterable[Feedback]) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(CSV_COLUMNS)
    for r in rows:
        w.writerow(
            _cell(v)
            for v in (
                r.id,
                r.created_at.isoformat(),
                r.type,
                r.rating,
                r.source_page,
                r.place_id,
                r.contact_email,
                r.content,
            )
        )
    return out.getvalue()
