"""H4 热点接口容量基准（start/submit/rank）

模拟 N 个游客并发执行「开局→3~5s 后结算(win)→拉榜」循环，输出 RPS/分位数。
只读基准不污染线上？submit 会真实落库——默认连本地/联调环境跑，连线上前确认。

用法（仓库根）：
    python scripts/bench_load.py --base http://localhost:8089 --users 20 --seconds 30
    python scripts/bench_load.py --base http://<host>:8089 --users 50 --seconds 60 --level 1

输出：
    start/submit/rank 各自 RPS、P50/P95/P99 延迟、错误数。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import random
import statistics
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "server" / ".env")

SIGN_SALT = os.getenv("ANTI_CHEAT_SALT", "Hd@2026!AntiCheat#7xQz$K9vM")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fmt_time(v: float) -> str:
    return str(int(v)) if v == int(v) else f"{v}"


class Timer:
    def __init__(self) -> None:
        self.lat: dict[str, list[float]] = {"start": [], "submit": [], "rank": []}
        self.errors = 0

    def record(self, kind: str, seconds: float) -> None:
        self.lat[kind].append(seconds * 1000)

    def stats(self, kind: str) -> dict:
        vals = sorted(self.lat[kind])
        n = len(vals)
        if not n:
            return {"n": 0}
        q = lambda p: vals[min(n - 1, int(n * p))]
        return {
            "n": n,
            "p50_ms": round(q(0.5), 1),
            "p95_ms": round(q(0.95), 1),
            "p99_ms": round(q(0.99), 1),
        }


async def worker(
    worker_id: int,
    base: str,
    level: int,
    seconds: int,
    timer: Timer,
    stop: asyncio.Event,
) -> None:
    async with httpx.AsyncClient(timeout=15, base_url=base) as client:
        # 1) 游客登录（每 worker 一个账号）
        r = await client.post("/api/auth/guest-login", json={"guest_uuid": f"bench-{worker_id}-{int(time.time())}"})
        if r.status_code != 200:
            timer.errors += 1
            return
        token = r.json()["data"]["token"]
        headers = {"Authorization": f"Bearer {token}"}

        while not stop.is_set():
            try:
                # 2) 开局会话（快路径，记录延迟）
                t0 = time.perf_counter()
                r = await client.post("/api/record/start", json={"level_id": level}, headers=headers)
                timer.record("start", time.perf_counter() - t0)
                if r.status_code != 200:
                    timer.errors += 1
                    continue
                session_id = r.json()["data"]["session_id"]

                # 3) 模拟真实游玩耗时（≥ 最短通关 3s + 随机余量）
                await asyncio.sleep(random.uniform(3.2, 5.0))
                clear_time = random.uniform(8, 30)
                ts = int(time.time())
                sign = _sha256(f"{level}{_fmt_time(clear_time)}{ts}{SIGN_SALT}")
                t0 = time.perf_counter()
                r = await client.post(
                    "/api/record/submit",
                    json={
                        "level_id": level,
                        "clear_time": clear_time,
                        "outcome": "win",
                        "timestamp": ts,
                        "sign": sign,
                        "session_id": session_id,
                    },
                    headers=headers,
                )
                timer.record("submit", time.perf_counter() - t0)
                if r.status_code != 200:
                    timer.errors += 1
                    continue

                # 4) 拉榜（热路径）
                t0 = time.perf_counter()
                r = await client.get("/api/record/rank", params={"level_id": level, "limit": 50}, headers=headers)
                timer.record("rank", time.perf_counter() - t0)
                if r.status_code != 200:
                    timer.errors += 1
            except httpx.HTTPError:
                timer.errors += 1
                await asyncio.sleep(1)


async def main() -> None:
    parser = argparse.ArgumentParser(description="H4 热点接口压测（start/submit/rank）")
    parser.add_argument("--base", default="http://localhost:8089")
    parser.add_argument("--users", type=int, default=10, help="并发游客数")
    parser.add_argument("--seconds", type=int, default=30, help="压测时长")
    parser.add_argument("--level", type=int, default=1, help="目标关卡")
    args = parser.parse_args()

    timer = Timer()
    stop = asyncio.Event()
    tasks = [asyncio.create_task(worker(i, args.base, args.level, args.seconds, timer, stop)) for i in range(args.users)]
    print(f"[i] 压测开始: users={args.users} duration={args.seconds}s base={args.base} level={args.level}")
    t0 = time.perf_counter()
    await asyncio.sleep(args.seconds)
    stop.set()
    await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.perf_counter() - t0

    print(f"\n[✓] 结束: 实际耗时 {elapsed:.1f}s  请求错误 {timer.errors}")
    for kind in ("start", "submit", "rank"):
        s = timer.stats(kind)
        if s["n"]:
            rps = s["n"] / elapsed
            print(f"  {kind:>6}: rps={rps:.1f}  n={s['n']}  p50={s['p50_ms']}ms  p95={s['p95_ms']}ms  p99={s['p99_ms']}ms")


if __name__ == "__main__":
    asyncio.run(main())
