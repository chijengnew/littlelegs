"""主機時鐘與 Google 有偏差時的 ID Token 驗證：容許 TOKEN_CLOCK_SKEW_S 秒；刪帳 5 分鐘窗口同樣加上這段誤差。

以測試用 RSA 金鑰簽出 Firebase 格式的 ID Token，憑證下載與目前時間以 fake 取代，不連網。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import firebase_admin
import google.auth.credentials
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from firebase_admin import auth, credentials
from google.auth import _helpers, crypt, jwt
from google.oauth2 import id_token

from app.errors import ApiError
from app.security.firebase import TOKEN_CLOCK_SKEW_S, AuthClaims, FirebaseVerifier
from app.services.deletion import REAUTH_WINDOW_S, request_account_deletion

PROJECT = "skew-test"
KID = "test-key"
NOW = datetime(2026, 11, 12, 4, 0, tzinfo=UTC)
NOW_S = int(NOW.timestamp())
TOKEN_TTL_S = 3600


class AnonymousCredential(credentials.Base):
    def get_credential(self) -> google.auth.credentials.Credentials:
        return google.auth.credentials.AnonymousCredentials()


@pytest.fixture(scope="module")
def keys() -> tuple[bytes, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return private, public.decode()


@pytest.fixture
def firebase_app(keys, monkeypatch):
    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)
    monkeypatch.setattr(id_token, "_fetch_certs", lambda request, url: {KID: keys[1]})
    monkeypatch.setattr(_helpers, "utcnow", lambda: NOW.replace(tzinfo=None))
    app = firebase_admin.initialize_app(AnonymousCredential(), options={"projectId": PROJECT})
    yield
    firebase_admin.delete_app(app)


def sign(keys: tuple[bytes, str], iat: int) -> str:
    signer = crypt.RSASigner.from_string(keys[0], key_id=KID)
    payload = {
        "iss": f"https://securetoken.google.com/{PROJECT}",
        "aud": PROJECT,
        "sub": "u1",
        "iat": iat,
        "exp": iat + TOKEN_TTL_S,
        "auth_time": iat,
        "email_verified": True,
        "firebase": {"sign_in_provider": "password"},
    }
    return jwt.encode(signer, payload).decode()


def test_skew_is_within_firebase_limit():
    assert 0 < TOKEN_CLOCK_SKEW_S <= 60


def test_without_skew_a_token_from_a_slow_host_view_is_rejected(firebase_app, keys):
    with pytest.raises(auth.InvalidIdTokenError, match="Token used too early"):
        auth.verify_id_token(sign(keys, NOW_S + 8))


@pytest.mark.parametrize(
    "iat",
    [NOW_S + 8, NOW_S + TOKEN_CLOCK_SKEW_S, NOW_S - TOKEN_TTL_S - TOKEN_CLOCK_SKEW_S],
    ids=["host-slow-7.6s", "host-slow-at-limit", "host-fast-at-limit"],
)
@pytest.mark.anyio
async def test_token_within_skew_is_accepted(firebase_app, keys, iat):
    claims = await FirebaseVerifier(PROJECT).verify_id_token(sign(keys, iat), check_revoked=False)
    assert (claims.uid, claims.auth_time, claims.email_verified) == ("u1", iat, True)


@pytest.mark.parametrize(
    ("iat", "code"),
    [
        (NOW_S + TOKEN_CLOCK_SKEW_S + 1, "AUTH_TOKEN_INVALID"),
        (NOW_S - TOKEN_TTL_S - TOKEN_CLOCK_SKEW_S - 1, "AUTH_TOKEN_EXPIRED"),
    ],
    ids=["issued-beyond-skew", "expired-beyond-skew"],
)
@pytest.mark.anyio
async def test_token_beyond_skew_is_rejected(firebase_app, keys, iat, code):
    with pytest.raises(ApiError) as e:
        await FirebaseVerifier(PROJECT).verify_id_token(sign(keys, iat), check_revoked=False)
    assert (e.value.status, e.value.code) == (401, code)


@pytest.mark.parametrize("check_revoked", [False, True])
@pytest.mark.anyio
async def test_skew_is_passed_with_and_without_revocation_check(firebase_app, monkeypatch, check_revoked):
    seen: list[tuple[object, bool, int]] = []

    def fake_verify(token, app=None, check_revoked=False, clock_skew_seconds=0):
        seen.append((app, check_revoked, clock_skew_seconds))
        return {"uid": "u1", "email_verified": True}

    monkeypatch.setattr(auth, "verify_id_token", fake_verify)
    await FirebaseVerifier(PROJECT).verify_id_token("token", check_revoked=check_revoked)
    assert seen == [(None, check_revoked, TOKEN_CLOCK_SKEW_S)]


class ReachedMemberLookup(Exception):
    pass


def deletion_state(auth_time: int | None) -> SimpleNamespace:
    class Verifier:
        async def verify_id_token(self, token: str, check_revoked: bool) -> AuthClaims:
            assert check_revoked
            return AuthClaims("u1", auth_time, "password", True)

    def factory():
        raise ReachedMemberLookup

    return SimpleNamespace(verifier=Verifier(), clock=lambda: NOW, factory=factory)


@pytest.mark.parametrize(
    "auth_time",
    [NOW_S - REAUTH_WINDOW_S - TOKEN_CLOCK_SKEW_S, NOW_S - REAUTH_WINDOW_S, NOW_S + TOKEN_CLOCK_SKEW_S],
    ids=["window-plus-skew", "window", "host-slow-at-limit"],
)
@pytest.mark.anyio
async def test_account_deletion_accepts_recent_sign_in_with_skew(auth_time):
    with pytest.raises(ReachedMemberLookup):
        await request_account_deletion(deletion_state(auth_time), "token", uuid.uuid4())


@pytest.mark.parametrize(
    "auth_time", [NOW_S - REAUTH_WINDOW_S - TOKEN_CLOCK_SKEW_S - 1, None], ids=["beyond-window", "missing"]
)
@pytest.mark.anyio
async def test_account_deletion_requires_recent_sign_in(auth_time):
    with pytest.raises(ApiError) as e:
        await request_account_deletion(deletion_state(auth_time), "token", uuid.uuid4())
    assert (e.value.status, e.value.code) == (401, "REAUTH_REQUIRED")
