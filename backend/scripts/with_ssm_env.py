"""從 Parameter Store 讀取機密放進環境變數，再以 exec 啟動指定程式（正式環境 systemd 使用）。

機密只存在於子程序的環境變數，不寫入磁碟、日誌或 shell 歷史；輸出只列參數名稱，不列值。
參數路徑下每個參數的最後一段名稱即環境變數名稱（只接受大寫英數與底線），例如
/littlelegs/prod/DATABASE_URL → DATABASE_URL。只讀取該路徑的直接子參數（不遞迴）。

用法：python -m scripts.with_ssm_env --path /littlelegs/prod -- uvicorn app.main:app ...
區域取自 AWS_DEFAULT_REGION（boto3 預設讀取的變數；於 /etc/littlelegs/api.env 明確設定），未設定時改用 AWS_REGION。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Mapping, Sequence

ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


def fetch_parameters(ssm, path: str) -> dict[str, str]:
    """回傳 {環境變數名稱: 值}；名稱不合法或重複時直接失敗，避免靜默略過。"""
    prefix = path.rstrip("/") + "/"
    out: dict[str, str] = {}
    for page in ssm.get_paginator("get_parameters_by_path").paginate(
        Path=prefix.rstrip("/"), Recursive=False, WithDecryption=True
    ):
        for p in page.get("Parameters", []):
            name = p["Name"]
            if not name.startswith(prefix):
                raise SystemExit(f"參數不在指定路徑下：{name}")
            key = name[len(prefix) :]
            if not ENV_NAME.match(key):
                raise SystemExit(f"參數名稱不是合法的環境變數名稱：{name}")
            if key in out:
                raise SystemExit(f"參數名稱重複：{name}")
            out[key] = p["Value"]
    return out


def merged_env(base: Mapping[str, str], secrets: Mapping[str, str]) -> dict[str, str]:
    """Parameter Store 的值優先，避免舊的環境檔或殘留變數蓋過機密。"""
    env = dict(base)
    env.update(secrets)
    return env


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--path", required=True, help="Parameter Store 路徑，例如 /littlelegs/prod")
    ap.add_argument("command", nargs=argparse.REMAINDER, help="-- 之後為要執行的程式與參數")
    args = ap.parse_args(argv)
    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not cmd:
        ap.error("請在 -- 之後指定要執行的程式")
    if not args.path.startswith("/"):
        ap.error("--path 必須以 / 開頭")

    import boto3

    try:
        region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
        secrets = fetch_parameters(boto3.client("ssm", region_name=region), args.path)
    except Exception as e:
        raise SystemExit(f"讀取 Parameter Store 失敗（{type(e).__name__}）：{e}") from None
    if not secrets:
        raise SystemExit(f"Parameter Store 路徑 {args.path} 下沒有任何參數")
    print(f"已載入 {len(secrets)} 個參數：{', '.join(sorted(secrets))}", file=sys.stderr, flush=True)
    os.execvpe(cmd[0], cmd, merged_env(os.environ, secrets))


if __name__ == "__main__":
    main()
