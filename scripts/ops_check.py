"""线上健康快速检查（F3：cron 友好，非 0 退出即告警）

检查项：
  1. GET /health                      服务存活
  2. GET /api/admin/monitor           本进程请求量/5xx 近一分钟/慢请求
  3. GET /api/admin/errors            未确认前端错误数
  4. GET /api/shop/admin/orders       待支付订单数（防漏单堆积）
  5. GET /api/admin/stats/overview    昨日活跃/对局粗看

用法：
    python scripts/ops_check.py                       # 读 server/.env 的 ADMIN_TOKEN，默认本机 8089
    python scripts/ops_check.py --base http://<host>:8089 --token xxx --json
退出码：0 全部健康；1 任一检查失败或超过阈值（--json 时输出机器可读结果）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "server" / ".env")

# 阈值（可按运营节奏调整）
MAX_ERRORS_UNACK = 50        # 未确认前端错误超过则告警
MAX_PENDING_ORDERS = 20      # 待支付订单堆积超过则告警
MAX_5XX_PER_MINUTE = 10      # 服务端 5xx 每分钟阈值（与 ALERT_ERROR_PER_MINUTE 一致）


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default=os.getenv("ADMIN_BASE_URL", "http://localhost:8089"), help="后端地址")
    parser.add_argument("--token", default=os.getenv("ADMIN_TOKEN", ""), help="X-Admin-Token")
    parser.add_argument("--json", action="store_true", help="输出 JSON（cron/告警网关友好）")
    args = parser.parse_args()

    if not args.token:
        print("[x] 缺少 ADMIN_TOKEN（参数 --token 或 env ADMIN_TOKEN）" if args.json else "[x] 缺少 ADMIN_TOKEN")
        return 2

    base = args.base.rstrip("/")
    headers = {"X-Admin-Token": args.token}
    report: dict[str, object] = {}
    problems: list[str] = []

    with httpx.Client(timeout=10) as client:
        try:
            health = client.get(f"{base}/health")
            report["health"] = health.status_code
            if health.status_code != 200:
                problems.append(f"health http {health.status_code}")
        except httpx.HTTPError as e:
            report["health"] = "unreachable"
            problems.append(f"health unreachable: {e}")

        def admin_get(path: str) -> dict | None:
            try:
                r = client.get(f"{base}{path}", headers=headers)
                if r.status_code != 200:
                    problems.append(f"{path} http {r.status_code}")
                    return None
                body = r.json()
                return body.get("data")
            except httpx.HTTPError as e:
                problems.append(f"{path} 请求失败: {e}")
                return None

        mon = admin_get("/api/admin/monitor")
        if mon is not None:
            report["monitor"] = {
                "uptime_seconds": mon.get("uptime_seconds"),
                "requests": mon.get("requests"),
                "errors_5xx_last_minute": mon.get("errors_5xx_last_minute"),
                "slow_requests": mon.get("slow_requests"),
                "recent_errors": (mon.get("recent_errors") or [])[-3:],
            }
            if (mon.get("errors_5xx_last_minute") or 0) >= MAX_5XX_PER_MINUTE:
                problems.append(f"5xx/分钟 {mon.get('errors_5xx_last_minute')} >= {MAX_5XX_PER_MINUTE}")

        errs = admin_get("/api/admin/errors?acknowledged=0&page_size=1")
        if errs is not None:
            total = int(errs.get("total") or 0)
            report["unacked_errors"] = total
            if total > MAX_ERRORS_UNACK:
                problems.append(f"未确认前端错误 {total} > {MAX_ERRORS_UNACK}")

        orders = admin_get("/api/shop/admin/orders?status=pending&page_size=1")
        if orders is not None:
            total = int(orders.get("total") or 0)
            report["pending_orders"] = total
            if total > MAX_PENDING_ORDERS:
                problems.append(f"待支付订单 {total} > {MAX_PENDING_ORDERS}")

        stats = admin_get("/api/admin/stats/overview?days=3")
        if stats is not None:
            series = stats.get("series") or []
            report["last_3d"] = [
                {"date": s.get("date"), "active": s.get("active"), "games": s.get("games")}
                for s in series
            ]

    ok = len(problems) == 0
    report["ok"] = ok
    if ok:
        report["problems"] = []
    else:
        report["problems"] = problems

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for key, value in report.items():
            if key != "problems":
                print(f"[i] {key}: {value}")
        for p in problems:
            print(f"[x] {p}")
        print("[✓] 全部健康" if ok else f"[x] 存在 {len(problems)} 个问题")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
