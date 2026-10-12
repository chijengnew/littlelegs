from collections import defaultdict
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from models import FavoriteCreate, FavoriteRecord, HistoryCreate, HistoryRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository(Protocol):
    def list_history(self, uid: str) -> list[HistoryRecord]: ...
    def save_history(self, uid: str, body: HistoryCreate) -> HistoryRecord: ...
    def delete_history(self, uid: str, record_id: str) -> bool: ...
    def list_favorites(self, uid: str) -> list[FavoriteRecord]: ...
    def save_favorite(self, uid: str, body: FavoriteCreate) -> FavoriteRecord: ...
    def delete_favorite(self, uid: str, favorite_id: str) -> bool: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self._history: dict[str, dict[str, HistoryRecord]] = defaultdict(dict)
        self._favorites: dict[str, dict[str, FavoriteRecord]] = defaultdict(dict)

    def list_history(self, uid: str) -> list[HistoryRecord]:
        return sorted(self._history[uid].values(), key=lambda record: record.created_at, reverse=True)

    def save_history(self, uid: str, body: HistoryCreate) -> HistoryRecord:
        existing = self._history[uid].get(body.query_id)
        if existing:
            return existing
        record = HistoryRecord(**body.model_dump(), created_at=_now())
        self._history[uid][record.query_id] = record
        return record

    def delete_history(self, uid: str, record_id: str) -> bool:
        return self._history[uid].pop(record_id, None) is not None

    def list_favorites(self, uid: str) -> list[FavoriteRecord]:
        return sorted(self._favorites[uid].values(), key=lambda record: record.created_at, reverse=True)

    def save_favorite(self, uid: str, body: FavoriteCreate) -> FavoriteRecord:
        record = FavoriteRecord(**body.model_dump(), id=uuid4().hex, created_at=_now())
        self._favorites[uid][record.id] = record
        return record

    def delete_favorite(self, uid: str, favorite_id: str) -> bool:
        return self._favorites[uid].pop(favorite_id, None) is not None


_repository: Repository | None = None


def get_repository() -> Repository:
    global _repository
    if _repository is None:
        _repository = InMemoryRepository()
    return _repository