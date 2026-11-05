"""共用 fixture。AnyIO 的 pytest plugin 固定 asyncio backend（aiomysql 只支援 asyncio），不與 pytest-asyncio 混用。"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_CHECK_ENFORCE", "false")


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
