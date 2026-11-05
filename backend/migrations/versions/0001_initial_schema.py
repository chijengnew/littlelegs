"""initial schema（資料模型）

人工檢查重點：
- 主鍵 UUIDv7 以 BINARY(16) 標準位元組順序保存；識別碼字串使用 utf8mb4_0900_bin 精確比較。
- 時間點欄位 DATETIME(6) 約定為 UTC（連線 time_zone=+00:00）。
- places.coord_source_record_id 與 source_records 互相參照，外鍵於兩表建立後另行加入。

Revision ID: 0001
Revises: 
Create Date: 2026-10-20 00:11:46.276225

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = '0001'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('datasets',
    sa.Column('id', mysql.BINARY(16), nullable=False),
    sa.Column('dataset_key', sa.String(length=64, collation='utf8mb4_0900_bin'), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('provider', sa.String(length=255), nullable=True),
    sa.Column('source_url', sa.String(length=512), nullable=False),
    sa.Column('license', sa.String(length=255), nullable=False),
    sa.Column('license_url', sa.String(length=512), nullable=True),
    sa.Column('license_status', sa.String(length=16), nullable=False),
    sa.Column('license_checked_at', sa.Date(), nullable=True),
    sa.Column('source_updated_at', sa.String(length=64), nullable=True),
    sa.Column('downloaded_at', sa.Date(), nullable=True),
    sa.Column('crs', sa.String(length=64), nullable=True),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.Column('import_policy', sa.String(length=32), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
    sa.Column('updated_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dataset_key'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('places',
    sa.Column('id', mysql.BINARY(16), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('address', sa.String(length=512), nullable=True),
    sa.Column('city', sa.String(length=16), nullable=True),
    sa.Column('lat', mysql.DECIMAL(precision=9, scale=6), nullable=False),
    sa.Column('lon', mysql.DECIMAL(precision=9, scale=6), nullable=False),
    sa.Column('coord_source_record_id', mysql.BINARY(16), nullable=True),
    sa.Column('google_place_id', sa.String(length=255, collation='utf8mb4_0900_bin'), nullable=True),
    sa.Column('place_id_status', sa.String(length=24), server_default='none', nullable=False),
    sa.Column('place_id_checked_at', mysql.DATETIME(fsp=6), nullable=True),
    sa.Column('primary_type', sa.String(length=32), nullable=True),
    sa.Column('indoor', sa.String(length=16), nullable=True),
    sa.Column('indoor_confirmation', sa.String(length=16), server_default='unknown', nullable=False),
    sa.Column('indoor_source_type', sa.String(length=16), nullable=True),
    sa.Column('indoor_evidence_record_id', mysql.BINARY(16), nullable=True),
    sa.Column('indoor_evidence_note', sa.String(length=512), nullable=True),
    sa.Column('indoor_verified_at', mysql.DATETIME(fsp=6), nullable=True),
    sa.Column('source_stay_minutes', sa.SmallInteger(), nullable=True),
    sa.Column('source_stay_record_id', mysql.BINARY(16), nullable=True),
    sa.Column('service_status', sa.SmallInteger(), nullable=True),
    sa.Column('public_access', sa.Boolean(), nullable=True),
    sa.Column('removed_at', mysql.DATETIME(fsp=6), nullable=True),
    sa.Column('created_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
    sa.Column('updated_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
    sa.CheckConstraint("indoor IS NULL OR indoor IN ('indoor','outdoor','mixed')", name='ck_places_indoor'),
    sa.CheckConstraint("kind IN ('attraction','lodging')", name='ck_places_kind'),
    sa.CheckConstraint('source_stay_minutes IS NULL OR (source_stay_minutes BETWEEN 15 AND 360 AND MOD(source_stay_minutes, 15) = 0)', name='ck_places_stay'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('google_place_id'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_places_geo', 'places', ['kind', 'lat', 'lon'], unique=False)
    op.create_index('ix_places_name', 'places', ['kind', 'name'], unique=False)
    op.create_table('rate_counters',
    sa.Column('counter_key', sa.String(length=191, collation='utf8mb4_0900_bin'), nullable=False),
    sa.Column('window_start', mysql.DATETIME(fsp=6), nullable=False),
    sa.Column('count', sa.BigInteger(), nullable=False),
    sa.Column('purge_after', mysql.DATETIME(fsp=6), nullable=False),
    sa.PrimaryKeyConstraint('counter_key', 'window_start'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_rate_counters_expiry', 'rate_counters', ['purge_after'], unique=False)
    op.create_table('users',
    sa.Column('id', mysql.BINARY(16), nullable=False),
    sa.Column('firebase_uid', sa.String(length=128, collation='utf8mb4_0900_bin'), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='active', nullable=False),
    sa.Column('locale', sa.String(length=16), server_default='zh-TW', nullable=False),
    sa.Column('created_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
    sa.Column('updated_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
    sa.CheckConstraint("status IN ('active','deleting')", name='ck_users_status'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('firebase_uid'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('favorite_operations',
    sa.Column('user_id', mysql.BINARY(16), nullable=False),
    sa.Column('idempotency_key', mysql.BINARY(16), nullable=False),
    sa.Column('op_type', sa.String(length=16), nullable=False),
    sa.Column('request_fingerprint', sa.BINARY(length=32), nullable=False),
    sa.Column('fingerprint_version', sa.SmallInteger(), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('favorite_id', mysql.BINARY(16), nullable=True),
    sa.Column('expires_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.Column('created_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.CheckConstraint("op_type IN ('create','delete')", name='ck_favorite_operations_type'),
    sa.CheckConstraint("state IN ('completed','cancelled')", name='ck_favorite_operations_state'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'idempotency_key'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_favorite_operations_expiry', 'favorite_operations', ['expires_at'], unique=False)
    op.create_index('ix_favorite_operations_target', 'favorite_operations', ['user_id', 'favorite_id'], unique=False)
    op.create_table('histories',
    sa.Column('id', mysql.BINARY(16), nullable=False),
    sa.Column('user_id', mysql.BINARY(16), nullable=False),
    sa.Column('query_id', mysql.BINARY(16), nullable=False),
    sa.Column('schema_version', sa.SmallInteger(), nullable=False),
    sa.Column('conditions', sa.JSON(), nullable=False),
    sa.Column('conditions_fingerprint', sa.BINARY(length=32), nullable=False),
    sa.Column('fingerprint_version', sa.SmallInteger(), nullable=False),
    sa.Column('start_label', sa.String(length=20), nullable=True),
    sa.Column('end_label', sa.String(length=20), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('search_run_id', mysql.BINARY(16), nullable=True),
    sa.Column('search_lease_expires_at', mysql.DATETIME(fsp=6), nullable=True),
    sa.Column('plan_ordered', sa.Boolean(), server_default=sa.text('0'), nullable=False),
    sa.Column('revision', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('reasons', sa.JSON(), nullable=True),
    sa.Column('created_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.CheckConstraint("status IN ('searching','succeeded','partial','failed','guest_imported')", name='ck_histories_status'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'query_id', name='uq_histories_user_query'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_histories_list', 'histories', ['user_id', 'created_at', 'id'], unique=False)
    op.create_table('import_batches',
    sa.Column('id', mysql.BINARY(16), nullable=False),
    sa.Column('dataset_id', mysql.BINARY(16), nullable=False),
    sa.Column('mode', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('started_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.Column('finished_at', mysql.DATETIME(fsp=6), nullable=True),
    sa.Column('record_count', sa.Integer(), nullable=True),
    sa.Column('removed_count', sa.Integer(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.CheckConstraint("mode IN ('full','incremental')", name='ck_import_batches_mode'),
    sa.CheckConstraint("status IN ('running','succeeded','failed','partial')", name='ck_import_batches_status'),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ),
    sa.PrimaryKeyConstraint('id'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('place_age_exclusions',
    sa.Column('place_id', mysql.BINARY(16), nullable=False),
    sa.Column('min_age', sa.SmallInteger(), nullable=False),
    sa.Column('max_age', sa.SmallInteger(), nullable=False),
    sa.Column('source_type', sa.String(length=16), nullable=False),
    sa.Column('evidence_record_id', mysql.BINARY(16), nullable=True),
    sa.Column('evidence_note', sa.String(length=512), nullable=True),
    sa.Column('verified_at', mysql.DATETIME(fsp=6), nullable=True),
    sa.ForeignKeyConstraint(['place_id'], ['places.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('place_id', 'min_age', 'max_age'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('place_age_ranges',
    sa.Column('place_id', mysql.BINARY(16), nullable=False),
    sa.Column('min_age', sa.SmallInteger(), nullable=False),
    sa.Column('max_age', sa.SmallInteger(), nullable=False),
    sa.Column('confirmation', sa.String(length=16), nullable=False),
    sa.Column('source_type', sa.String(length=16), nullable=False),
    sa.Column('evidence_record_id', mysql.BINARY(16), nullable=True),
    sa.Column('evidence_note', sa.String(length=512), nullable=True),
    sa.Column('verified_at', mysql.DATETIME(fsp=6), nullable=True),
    sa.CheckConstraint('min_age BETWEEN 0 AND 18 AND max_age BETWEEN 0 AND 18 AND min_age <= max_age', name='ck_place_age_ranges_bounds'),
    sa.ForeignKeyConstraint(['place_id'], ['places.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('place_id', 'min_age', 'max_age'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('place_facilities',
    sa.Column('place_id', mysql.BINARY(16), nullable=False),
    sa.Column('facility', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=8), nullable=False),
    sa.Column('confirmation', sa.String(length=16), nullable=False),
    sa.Column('source_type', sa.String(length=16), nullable=False),
    sa.Column('evidence_record_id', mysql.BINARY(16), nullable=True),
    sa.Column('evidence_note', sa.String(length=512), nullable=True),
    sa.Column('verified_at', mysql.DATETIME(fsp=6), nullable=True),
    sa.CheckConstraint("status IN ('yes','no','unknown')", name='ck_place_facilities_status'),
    sa.ForeignKeyConstraint(['place_id'], ['places.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('place_id', 'facility'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('place_id_aliases',
    sa.Column('google_place_id', sa.String(length=255, collation='utf8mb4_0900_bin'), nullable=False),
    sa.Column('place_id', mysql.BINARY(16), nullable=False),
    sa.Column('reason', sa.String(length=64), nullable=False),
    sa.Column('created_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
    sa.ForeignKeyConstraint(['place_id'], ['places.id'], ),
    sa.PrimaryKeyConstraint('google_place_id'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('place_types',
    sa.Column('place_id', mysql.BINARY(16), nullable=False),
    sa.Column('type', sa.String(length=32), nullable=False),
    sa.Column('confirmation', sa.String(length=16), nullable=False),
    sa.Column('source_type', sa.String(length=16), nullable=False),
    sa.Column('evidence_record_id', mysql.BINARY(16), nullable=True),
    sa.Column('evidence_note', sa.String(length=512), nullable=True),
    sa.Column('verified_at', mysql.DATETIME(fsp=6), nullable=True),
    sa.ForeignKeyConstraint(['place_id'], ['places.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('place_id', 'type'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('private_endpoints',
    sa.Column('id', mysql.BINARY(16), nullable=False),
    sa.Column('user_id', mysql.BINARY(16), nullable=False),
    sa.Column('google_place_id', sa.String(length=255, collation='utf8mb4_0900_bin'), nullable=False),
    sa.Column('created_at', mysql.DATETIME(fsp=6), server_default=sa.text('CURRENT_TIMESTAMP(6)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('query_operations',
    sa.Column('user_id', mysql.BINARY(16), nullable=False),
    sa.Column('query_id', mysql.BINARY(16), nullable=False),
    sa.Column('request_fingerprint', sa.BINARY(length=32), nullable=False),
    sa.Column('fingerprint_version', sa.SmallInteger(), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('expires_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.Column('created_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.CheckConstraint("state IN ('created','deleted')", name='ck_query_operations_state'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'query_id'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_query_operations_expiry', 'query_operations', ['expires_at'], unique=False)
    op.create_table('favorites',
    sa.Column('id', mysql.BINARY(16), nullable=False),
    sa.Column('user_id', mysql.BINARY(16), nullable=False),
    sa.Column('content_fingerprint', sa.BINARY(length=32), nullable=False),
    sa.Column('fingerprint_version', sa.SmallInteger(), nullable=False),
    sa.Column('source_history_id', mysql.BINARY(16), nullable=True),
    sa.Column('schema_version', sa.SmallInteger(), nullable=False),
    sa.Column('conditions', sa.JSON(), nullable=False),
    sa.Column('start_label', sa.String(length=20), nullable=True),
    sa.Column('end_label', sa.String(length=20), nullable=True),
    sa.Column('saved_as', sa.String(length=16), nullable=False),
    sa.Column('reasons', sa.JSON(), nullable=True),
    sa.Column('created_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.CheckConstraint("saved_as IN ('plan','unverified','infeasible')", name='ck_favorites_saved_as'),
    sa.ForeignKeyConstraint(['source_history_id'], ['histories.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'content_fingerprint', name='uq_favorites_user_content'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_favorites_list', 'favorites', ['user_id', 'created_at', 'id'], unique=False)
    op.create_table('history_stops',
    sa.Column('history_id', mysql.BINARY(16), nullable=False),
    sa.Column('order_index', sa.SmallInteger(), nullable=False),
    sa.Column('place_id', mysql.BINARY(16), nullable=False),
    sa.Column('stay_minutes', sa.SmallInteger(), nullable=False),
    sa.Column('stay_source', sa.String(length=16), nullable=False),
    sa.Column('day_index', sa.SmallInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('selected_google_place_id', sa.String(length=255, collation='utf8mb4_0900_bin'), nullable=True),
    sa.CheckConstraint("stay_source IN ('user','source','type_default')", name='ck_history_stops_source'),
    sa.CheckConstraint('stay_minutes BETWEEN 15 AND 360 AND MOD(stay_minutes, 15) = 0', name='ck_history_stops_stay'),
    sa.ForeignKeyConstraint(['history_id'], ['histories.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['place_id'], ['places.id'], ),
    sa.PrimaryKeyConstraint('history_id', 'order_index'),
    sa.UniqueConstraint('history_id', 'place_id', name='uq_history_stops_place'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('private_endpoint_aliases',
    sa.Column('user_id', mysql.BINARY(16), nullable=False),
    sa.Column('google_place_id', sa.String(length=255, collation='utf8mb4_0900_bin'), nullable=False),
    sa.Column('endpoint_id', mysql.BINARY(16), nullable=False),
    sa.ForeignKeyConstraint(['endpoint_id'], ['private_endpoints.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'google_place_id'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('source_records',
    sa.Column('id', mysql.BINARY(16), nullable=False),
    sa.Column('dataset_id', mysql.BINARY(16), nullable=False),
    sa.Column('source_key', sa.String(length=255, collation='utf8mb4_0900_bin'), nullable=False),
    sa.Column('place_id', mysql.BINARY(16), nullable=True),
    sa.Column('first_batch_id', mysql.BINARY(16), nullable=False),
    sa.Column('last_seen_batch_id', mysql.BINARY(16), nullable=False),
    sa.Column('removed_at', mysql.DATETIME(fsp=6), nullable=True),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('address', sa.String(length=512), nullable=True),
    sa.Column('city', sa.String(length=16), nullable=True),
    sa.Column('lat', mysql.DECIMAL(precision=9, scale=6), nullable=True),
    sa.Column('lon', mysql.DECIMAL(precision=9, scale=6), nullable=True),
    sa.Column('coord_note', sa.String(length=255), nullable=True),
    sa.Column('source_updated_at', sa.String(length=64), nullable=True),
    sa.Column('service_status', sa.SmallInteger(), nullable=True),
    sa.Column('public_access', sa.Boolean(), nullable=True),
    sa.Column('display', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ),
    sa.ForeignKeyConstraint(['first_batch_id'], ['import_batches.id'], ),
    sa.ForeignKeyConstraint(['last_seen_batch_id'], ['import_batches.id'], ),
    sa.ForeignKeyConstraint(['place_id'], ['places.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dataset_id', 'source_key', name='uq_source_records_dataset_key'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_source_records_place', 'source_records', ['place_id'], unique=False)
    op.create_table('favorite_aliases',
    sa.Column('old_favorite_id', mysql.BINARY(16), nullable=False),
    sa.Column('user_id', mysql.BINARY(16), nullable=False),
    sa.Column('favorite_id', mysql.BINARY(16), nullable=False),
    sa.ForeignKeyConstraint(['favorite_id'], ['favorites.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('old_favorite_id'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('favorite_stops',
    sa.Column('favorite_id', mysql.BINARY(16), nullable=False),
    sa.Column('order_index', sa.SmallInteger(), nullable=False),
    sa.Column('place_id', mysql.BINARY(16), nullable=False),
    sa.Column('stay_minutes', sa.SmallInteger(), nullable=False),
    sa.Column('stay_source', sa.String(length=16), nullable=False),
    sa.Column('day_index', sa.SmallInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('selected_google_place_id', sa.String(length=255, collation='utf8mb4_0900_bin'), nullable=True),
    sa.CheckConstraint("stay_source IN ('user','source','type_default')", name='ck_favorite_stops_source'),
    sa.CheckConstraint('stay_minutes BETWEEN 15 AND 360 AND MOD(stay_minutes, 15) = 0', name='ck_favorite_stops_stay'),
    sa.ForeignKeyConstraint(['favorite_id'], ['favorites.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['place_id'], ['places.id'], ),
    sa.PrimaryKeyConstraint('favorite_id', 'order_index'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_engine='InnoDB'
    )
    op.create_foreign_key('fk_places_coord_source_record', 'places', 'source_records',
                          ['coord_source_record_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema.

    注意：刪表會一併刪除索引；MySQL 不允許先刪除外鍵使用中的索引，故不逐一 drop_index。
    正式環境執行前先確認備份與修復方式。
    """
    op.drop_constraint('fk_places_coord_source_record', 'places', type_='foreignkey')
    op.drop_table('favorite_stops')
    op.drop_table('favorite_aliases')
    op.drop_table('source_records')
    op.drop_table('private_endpoint_aliases')
    op.drop_table('history_stops')
    op.drop_table('favorites')
    op.drop_table('query_operations')
    op.drop_table('private_endpoints')
    op.drop_table('place_types')
    op.drop_table('place_id_aliases')
    op.drop_table('place_facilities')
    op.drop_table('place_age_ranges')
    op.drop_table('place_age_exclusions')
    op.drop_table('import_batches')
    op.drop_table('histories')
    op.drop_table('favorite_operations')
    op.drop_table('users')
    op.drop_table('rate_counters')
    op.drop_table('places')
    op.drop_table('datasets')
