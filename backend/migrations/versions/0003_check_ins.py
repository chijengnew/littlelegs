"""check_ins、check_in_operations：探險護照的到訪紀錄與蓋章冪等操作

同一會員、同一景點最多一筆到訪紀錄；不保存當次座標、精確度或計算距離。
操作紀錄不對到訪紀錄設外鍵，刪除後仍保留至操作窗口結束，避免延遲重送讓紀錄復活。

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-13 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "check_ins",
        sa.Column("id", mysql.BINARY(length=16), nullable=False),
        sa.Column("user_id", mysql.BINARY(length=16), nullable=False),
        sa.Column("place_id", mysql.BINARY(length=16), nullable=False),
        sa.Column("verification_method", sa.String(length=16), nullable=False),
        sa.Column("visited_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("verified_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.CheckConstraint("verification_method IN ('location','manual')", name="ck_check_ins_method"),
        sa.CheckConstraint(
            "(verification_method = 'location') = (verified_at IS NOT NULL)", name="ck_check_ins_verified"
        ),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "place_id", name="uq_check_ins_user_place"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
        mysql_engine="InnoDB",
    )
    op.create_index("ix_check_ins_list", "check_ins", ["user_id", "created_at", "id"], unique=False)
    op.create_table(
        "check_in_operations",
        sa.Column("user_id", mysql.BINARY(length=16), nullable=False),
        sa.Column("idempotency_key", mysql.BINARY(length=16), nullable=False),
        sa.Column("request_fingerprint", sa.BINARY(length=32), nullable=False),
        sa.Column("fingerprint_version", sa.SmallInteger(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("check_in_id", mysql.BINARY(length=16), nullable=False),
        sa.Column("expires_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.CheckConstraint("state IN ('completed','cancelled')", name="ck_check_in_operations_state"),
        sa.CheckConstraint("outcome IN ('created','upgraded','existing')", name="ck_check_in_operations_outcome"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "idempotency_key"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_check_in_operations_expiry", "check_in_operations", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_check_in_operations_target", "check_in_operations", ["user_id", "check_in_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_check_in_operations_target", table_name="check_in_operations")
    op.drop_index("ix_check_in_operations_expiry", table_name="check_in_operations")
    op.drop_table("check_in_operations")
    op.drop_index("ix_check_ins_list", table_name="check_ins")
    op.drop_table("check_ins")
