"""回饋的輸入驗證與匯出格式。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.db.models import Feedback
from app.db.session import build_engine
from app.domain.schemas import FeedbackIn
from app.services.feedback import CSV_COLUMNS, rows_to_csv

PLACE = "0190a000-0000-7000-8000-000000000002"
OK = {"type": "suggestion", "content": "很好用"}


def test_minimal_feedback_defaults_to_other_source():
    f = FeedbackIn.model_validate(OK)
    assert (f.source_page, f.rating, f.contact_email, f.place_id) == ("other", None, None, None)


@pytest.mark.parametrize("n", [1, 5])
def test_rating_range_ok(n):
    assert FeedbackIn.model_validate({**OK, "rating": n}).rating == n


@pytest.mark.parametrize(
    "bad",
    [
        {"type": "hack"},
        {"rating": 0},
        {"rating": 6},
        {"content": ""},
        {"content": "   "},
        {"content": "字" * 1001},
        {"contact_email": "not-an-email"},
        {"contact_email": "a b@example.com"},
        {"contact_email": f"{'a' * 250}@b.co"},
        {"source_page": "/account/favorites/私人紀錄"},
        {"place_id": "not-a-uuid"},
        {"place_id": PLACE},
        {"url": "https://example.com"},
        {"user_id": "u1"},
    ],
)
def test_invalid_input_rejected(bad):
    with pytest.raises(ValidationError):
        FeedbackIn.model_validate({**OK, **bad})


def test_max_length_and_place_for_place_data_accepted():
    f = FeedbackIn.model_validate(
        {"type": "place_data", "content": "字" * 1000, "contact_email": "a@example.com", "place_id": PLACE}
    )
    assert f.place_id == PLACE and len(f.content) == 1000


def _row(content: str, email: str | None = None) -> Feedback:
    return Feedback(
        id=uuid.UUID(PLACE),
        type="other",
        rating=None,
        content=content,
        contact_email=email,
        source_page="footer",
        place_id=None,
        created_at=datetime(2026, 11, 5, tzinfo=UTC),
    )


def test_csv_has_header_and_escapes_formula_cells():
    out = rows_to_csv([_row('=HYPERLINK("x")', "+886@example.com"), _row("一般內容")]).splitlines()
    assert out[0] == ",".join(CSV_COLUMNS)
    assert "'=HYPERLINK" in out[1] and "'+886@example.com" in out[1]
    assert out[2].endswith(",一般內容")


def test_engine_hides_parameters_from_error_messages():
    eng = build_engine(Settings(env="test", database_url="mysql+aiomysql://u:p@127.0.0.1:3306/x"))
    assert eng.sync_engine.hide_parameters is True


def test_settings_repr_hides_secrets():
    text = repr(Settings(env="test", database_url="mysql://u:secret-pass@h/x", google_server_api_key="secret-key"))
    assert "secret-pass" not in text and "secret-key" not in text
    assert "env='test'" in text
