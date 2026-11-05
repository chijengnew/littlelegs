"""匯出 OpenAPI（不啟動伺服器、不需機密或資料庫）。CI 以此重新產生前端型別並比對差異。

用法：python -m scripts.export_openapi > openapi.json
"""

from __future__ import annotations

import json
import sys

from app.main import create_app

if __name__ == "__main__":
    json.dump(create_app().openapi(), sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
