"""查看與處理使用者回饋（沒有管理後台）。輸出可能含個人資料：不要提交到 Git，也不要貼到公開的地方。

python -m scripts.feedback export                          # 全部輸出到畫面
python -m scripts.feedback export --since 2026-11-01       # 只看某天（台北日期）之後
python -m scripts.feedback export --email a@example.com    # 當事人查詢：依送出時填的信箱
python -m scripts.feedback export --out feedback.csv       # 存成只有自己可讀的檔案
python -m scripts.feedback delete --id <回饋編號>           # 當事人申請刪除
"""

from __future__ import annotations

import argparse
import asyncio
import os
import uuid
from datetime import date

from app.services import feedback

from ._common import db


async def run(args: argparse.Namespace) -> str:
    _, eng, factory = db()
    try:
        if args.command == "delete":
            found = await feedback.delete_one(factory, uuid.UUID(args.id))
            return "已刪除" if found else "找不到這筆回饋"
        rows = await feedback.find(factory, since=args.since, email=args.email)
        return feedback.rows_to_csv(rows)
    finally:
        await eng.dispose()


def main() -> None:
    p = argparse.ArgumentParser(description="查看與處理使用者回饋")
    sub = p.add_subparsers(dest="command", required=True)
    ex = sub.add_parser("export", help="輸出 CSV")
    ex.add_argument("--since", type=date.fromisoformat, help="只輸出這一天（台北日期）之後的回饋")
    ex.add_argument("--email", help="只輸出這個聯絡信箱的回饋")
    ex.add_argument("--out", help="寫入檔案（權限 600）；預設輸出到畫面")
    rm = sub.add_parser("delete", help="刪除一筆回饋")
    rm.add_argument("--id", required=True, help="回饋編號")
    args = p.parse_args()
    result = asyncio.run(run(args))
    if args.command == "export" and args.out:
        with os.fdopen(os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
            f.write(result)
    else:
        print(result)


if __name__ == "__main__":
    main()
