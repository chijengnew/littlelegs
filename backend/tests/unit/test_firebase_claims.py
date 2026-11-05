"""ID Token 內容 → AuthClaims：email_verified 只有明確為 True 才算已驗證。"""

from __future__ import annotations

import pytest

from app.security.firebase import claims_from_decoded


def test_password_account_verified_and_provider():
    c = claims_from_decoded(
        {"uid": "u1", "auth_time": 1_800_000_000, "email_verified": True, "firebase": {"sign_in_provider": "password"}}
    )
    assert (c.uid, c.auth_time, c.sign_in_provider, c.email_verified) == ("u1", 1_800_000_000, "password", True)


@pytest.mark.parametrize("value", [False, None, "true", 1])
def test_email_verified_must_be_true(value):
    decoded = {"uid": "u1", "firebase": {"sign_in_provider": "password"}}
    if value is not None:
        decoded["email_verified"] = value
    assert claims_from_decoded(decoded).email_verified is False


def test_missing_firebase_section():
    c = claims_from_decoded({"uid": "u1", "email_verified": True})
    assert c.sign_in_provider is None and c.auth_time is None and c.email_verified is True
