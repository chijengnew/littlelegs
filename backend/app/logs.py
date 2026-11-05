"""日誌共用設定。"""

from __future__ import annotations

import logging


def quiet_http_client_logs() -> None:
    """HTTP 用戶端的 INFO 日誌會記錄完整請求網址（含天氣查詢的起點座標、Place ID），只保留警告以上。"""
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
