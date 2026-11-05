"""未完成註冊的判斷、取消註冊與逾期清理（Firebase、MySQL 以 fake 取代；鎖與會員查詢另有整合測試）。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.errors import ApiError
from app.security.firebase import AccountInfo, AuthClaims, account_info
from app.services import registration
from app.services.registration import cancel_registration, is_expired, is_pending, purge_expired

NOW = datetime(2026, 11, 2, 4, 0, tzinfo=UTC)
NOW_MS = int(NOW.timestamp() * 1000)
HOUR_MS = 3600 * 1000


def info(uid="u", verified=False, providers=("password",), created=NOW_MS - 25 * HOUR_MS) -> AccountInfo:
    return AccountInfo(uid, verified, providers, created)


@pytest.mark.parametrize(
    ("acct", "expected"),
    [
        (info(), True),
        (info(verified=True), False),
        (info(providers=("google.com", "password")), False),
        (info(providers=()), False),
    ],
)
def test_is_pending(acct, expected):
    assert is_pending(acct) is expected


def test_is_expired_boundary_and_unknown_creation_time():
    assert is_expired(info(created=NOW_MS - 24 * HOUR_MS), NOW)
    assert not is_expired(info(created=NOW_MS - 24 * HOUR_MS + 1), NOW)
    assert not is_expired(info(created=None), NOW)
    assert not is_expired(info(verified=True), NOW)


def test_account_info_from_admin_record():
    record = SimpleNamespace(
        uid="u1",
        email_verified=True,
        provider_data=[SimpleNamespace(provider_id="password"), SimpleNamespace(provider_id="google.com")],
        user_metadata=SimpleNamespace(creation_timestamp=123),
    )
    assert account_info(record) == AccountInfo("u1", True, ("password", "google.com"), 123)
    bare = account_info(SimpleNamespace(uid="u2", email_verified=None, provider_data=None))
    assert bare == AccountInfo("u2", False, (), None)


class FakeVerifier:
    def __init__(self, accounts: dict[str, AccountInfo], broken: frozenset[str] = frozenset()) -> None:
        self.accounts = accounts
        self.broken = broken
        self.deleted: list[str] = []

    async def verify_id_token(self, token: str, check_revoked: bool) -> AuthClaims:
        assert check_revoked
        return AuthClaims(token, None, "password")

    async def get_account(self, uid: str) -> AccountInfo | None:
        return self.accounts.get(uid)

    async def list_unverified_accounts(self) -> list[AccountInfo]:
        return [a for a in self.accounts.values() if not a.email_verified]

    async def delete_user(self, uid: str) -> None:
        if uid in self.broken:
            raise RuntimeError("firebase down")
        self.deleted.append(uid)
        self.accounts.pop(uid, None)


@pytest.fixture
def members(monkeypatch) -> set[str]:
    """以集合代替 MySQL 會員查詢；鎖改為記錄呼叫的 no-op。"""
    have: set[str] = set()
    locked: list[str] = []

    @asynccontextmanager
    async def fake_lock(engine, uid):
        locked.append(uid)
        yield

    async def fake_has_member(st, uid):
        assert locked and locked[-1] == uid
        return uid in have

    monkeypatch.setattr(registration, "uid_lock", fake_lock)
    monkeypatch.setattr(registration, "_has_member", fake_has_member)
    return have


def state(verifier: FakeVerifier) -> SimpleNamespace:
    return SimpleNamespace(verifier=verifier, engine=None)


@pytest.mark.anyio
async def test_cancel_deletes_pending_and_treats_missing_as_done(members):
    v = FakeVerifier({"p1": info("p1")})
    await cancel_registration(state(v), "p1")
    assert v.deleted == ["p1"]
    await cancel_registration(state(v), "p1")
    assert v.deleted == ["p1"]


@pytest.mark.parametrize(
    ("acct", "is_member"),
    [(info("x", verified=True), False), (info("x", providers=("google.com",)), False), (info("x"), True)],
)
@pytest.mark.anyio
async def test_cancel_refuses_verified_google_or_member(members, acct, is_member):
    if is_member:
        members.add("x")
    v = FakeVerifier({"x": acct})
    with pytest.raises(ApiError) as e:
        await cancel_registration(state(v), "x")
    assert (e.value.status, e.value.code) == (409, "REGISTRATION_COMPLETED") and v.deleted == []


@pytest.mark.anyio
async def test_purge_removes_only_expired_and_continues_after_failure(members):
    members.add("member-old")
    v = FakeVerifier(
        {
            "old": info("old"),
            "broken": info("broken"),
            "fresh": info("fresh", created=NOW_MS - HOUR_MS),
            "verified": info("verified", verified=True),
            "member-old": info("member-old"),
        },
        broken=frozenset({"broken"}),
    )
    out = await purge_expired(state(v), NOW)
    assert (out.removed, out.failures) == (1, 1) and v.deleted == ["old"]


def test_ttl_is_24_hours():
    assert registration.PENDING_TTL == timedelta(hours=24)
