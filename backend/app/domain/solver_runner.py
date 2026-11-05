"""在獨立、可取消、有併發上限的程序中執行排序演算法。

- 不阻塞事件迴圈；初期同時 1 件，排隊時間也計入整體期限。
- 演算法本身有內部預算（預設 5 秒）會回傳 search_incomplete；外層逾時則終止子程序（後盾）。
"""

from __future__ import annotations

import asyncio
import multiprocessing as mp
from multiprocessing.connection import Connection

from app.domain.scheduler import Problem, Solution, solve

_ctx = mp.get_context("forkserver")
try:
    _ctx.set_forkserver_preload(["app.domain.scheduler"])
except Exception:
    pass

_sem: asyncio.Semaphore | None = None


class SolverTimeout(Exception):
    pass


def _child(conn: Connection, problem: Problem, mode: str, budget: float) -> None:
    try:
        conn.send(("ok", solve(problem, mode, budget)))
    except Exception as e:
        conn.send(("error", repr(e)))
    finally:
        conn.close()


def configure(concurrency: int) -> None:
    global _sem
    _sem = asyncio.Semaphore(concurrency)


async def run_solver(problem: Problem, mode: str, budget_s: float, remaining_s: float) -> Solution:
    """remaining_s：整體請求剩餘期限（含排隊）。"""
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(1)
    loop = asyncio.get_running_loop()
    start = loop.time()
    try:
        await asyncio.wait_for(_sem.acquire(), timeout=max(0.01, remaining_s))
    except TimeoutError as e:
        raise SolverTimeout("排隊等待運算逾時") from e
    try:
        left = remaining_s - (loop.time() - start)
        budget = max(0.05, min(budget_s, left - 0.3))
        parent, child = _ctx.Pipe(duplex=False)
        proc = _ctx.Process(target=_child, args=(child, problem, mode, budget), daemon=True)
        proc.start()
        child.close()
        try:
            ready = await loop.run_in_executor(None, parent.poll, max(0.05, left - 0.1))
            if not ready:
                raise SolverTimeout("運算逾時")
            status, payload = parent.recv()
        finally:
            if proc.is_alive():
                proc.terminate()
            proc.join(timeout=1)
            parent.close()
        if status != "ok":
            raise RuntimeError(f"演算法程序錯誤：{payload}")
        return payload
    finally:
        _sem.release()
