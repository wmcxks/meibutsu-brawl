"""线上 MySQL 增量迁移脚本
直连 server/.env 中 MYSQL_ROOT_* 指向的线上 MySQL，
按文件名顺序执行 server/sql/migrations/*.sql（001 起），
用于把早期只建了 hd_users/hd_records/hd_cheat_logs 的库升级到最新结构。
"""
import asyncio
import os
import re
from pathlib import Path

import asyncmy
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / "server" / ".env"
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "server" / "sql" / "migrations"

load_dotenv(ENV_PATH)


def split_sql(sql: str) -> list[str]:
    """按分号拆分，剥离 -- 整行注释；支持插入语句内的中文分号不受影响。"""
    stmts = []
    for raw in sql.split(";"):
        lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            stmts.append(stmt)
    return stmts


async def main():
    host = os.environ["MYSQL_ROOT_HOST"]
    port = int(os.environ.get("MYSQL_ROOT_PORT", 3306))
    user = os.environ["MYSQL_ROOT_USER"]
    password = os.environ["MYSQL_ROOT_PASSWORD"]
    db = os.environ["MYSQL_ROOT_DATABASE"]

    print(f"[i] 连接 线上 MySQL {user}@{host}:{port}/{db} ...")
    conn = await asyncmy.connect(
        host=host, port=port, user=user, password=password, db=db, charset="utf8mb4"
    )
    try:
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            print(f"\n[i] ==== {path.name} ====")
            sql = path.read_text(encoding="utf-8")
            for stmt in split_sql(sql):
                first = re.sub(r"\s+", " ", stmt.splitlines()[0])[:100]
                print(f"[i] 执行: {first} ...")
                try:
                    await conn.cursor().execute(stmt)
                except Exception as e:
                    print(f"[!] 跳过（可能已存在/已执行）: {e}")
            await conn.commit()

        async with conn.cursor() as cur:
            await cur.execute("SHOW TABLES LIKE 'hd_%'")
            rows = await cur.fetchall()
            print("\n[i] 线上现有 hd_* 表：", [r[0] for r in rows])
    finally:
        await conn.ensure_closed()
    print("[✓] 迁移执行完成")


if __name__ == "__main__":
    asyncio.run(main())
