"""feedback：使用者回饋

不主動關聯會員帳號；source_page 只保存固定的頁面類型，不保存完整網址。

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-05 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", mysql.BINARY(length=16), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=True),
        sa.Column("content", sa.String(length=1000), nullable=False),
        sa.Column("contact_email", sa.String(length=254), nullable=True),
        sa.Column("source_page", sa.String(length=16), nullable=False),
        sa.Column("place_id", mysql.BINARY(length=16), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
        sa.CheckConstraint(
            "source_page IN ('planner','place_detail','saved_detail','footer','other')", name="ck_feedback_source"
        ),
        sa.CheckConstraint("type IN ('bug','place_data','suggestion','other')", name="ck_feedback_type"),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
        mysql_engine="InnoDB",
    )
    op.create_index("ix_feedback_created_at", "feedback", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_feedback_created_at", table_name="feedback")
    op.drop_table("feedback")
