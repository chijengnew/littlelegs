"""開發用啟動入口：在 backend 資料夾執行 `uvicorn main:app --reload`。"""

from app.main import app

__all__ = ["app"]
