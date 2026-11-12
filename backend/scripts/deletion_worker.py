"""刪除意圖處理工作：由 EC2 systemd timer 執行。

  run         每分鐘：處理所有未完成意圖（不只掃本地 deleting，避免漏掉「意圖成功、本地標記失敗」者）。
  reconcile   每日：未完成且超過 15 分鐘者告警；已完成者確認目標已不存在。
  replay-all  備份還原後（維護模式中）：重播所有仍保留的意圖，含已完成與早於還原點者。
  purge-unverified  每小時：刪除註冊滿 24 小時仍未驗證 Email 的 Firebase 帳號（未完成的註冊不保留）。

告警：以 ERROR 日誌並以非零結束碼退出，交由 systemd OnFailure= 通知。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.config import get_settings
from app.db.models import User
from app.main import default_state_factory
from app.services.deletion import RECORD_MODELS, process_intent
from app.services.registration import purge_expired

from ._common import setup_logging

log = logging.getLogger("littlelegs.deletion_worker")
ALERT_AFTER = timedelta(minutes=15)


def _state():
    settings = get_settings()
    st = default_state_factory(settings)
    st.google = None
    return st


async def run_pending(replay_all: bool = False) -> int:
    st = _state()
    failures = 0
    try:
        intents = await (st.intents.list_all() if replay_all else st.intents.list_pending())
        for it in sorted(intents, key=lambda i: i.accepted_at):
            try:
                await process_intent(st, it)
            except Exception:
                failures += 1
                log.exception("意圖處理失敗，下一輪重試 operation_id=%s kind=%s", it.operation_id, it.kind)
        log.info("processed=%d failures=%d replay_all=%s", len(intents), failures, replay_all)
    finally:
        await st.engine.dispose()
    return failures


async def reconcile() -> int:
    st = _state()
    problems = 0
    now = datetime.now(UTC)
    try:
        for it in await st.intents.list_all():
            done = await st.intents.is_completed(it.operation_id)
            if not done:
                if now - datetime.fromisoformat(it.accepted_at) > ALERT_AFTER:
                    problems += 1
                    log.error("刪除意圖超過 15 分鐘未完成 operation_id=%s kind=%s", it.operation_id, it.kind)
                continue
            async with st.factory() as s:
                if it.kind == "account":
                    left = (await s.execute(select(User.id).where(User.id == uuid.UUID(it.user_id)))).scalar()
                else:
                    model = RECORD_MODELS[it.kind]
                    left = (await s.execute(select(model.id).where(model.id == uuid.UUID(it.target_id)))).scalar()
            if left is not None:
                problems += 1
                log.error("已完成的刪除意圖目標仍存在（可能來自還原）operation_id=%s", it.operation_id)
    finally:
        await st.engine.dispose()
    return problems


async def purge_unverified() -> int:
    st = _state()
    try:
        out = await purge_expired(st, datetime.now(UTC))
        log.info("purged_unverified=%d failures=%d", out.removed, out.failures)
    finally:
        await st.engine.dispose()
    return out.failures


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "reconcile", "replay-all", "purge-unverified"])
    a = ap.parse_args()
    if a.cmd == "run":
        bad = asyncio.run(run_pending())
    elif a.cmd == "replay-all":
        bad = asyncio.run(run_pending(replay_all=True))
    elif a.cmd == "purge-unverified":
        bad = asyncio.run(purge_unverified())
    else:
        bad = asyncio.run(reconcile())
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
