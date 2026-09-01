"""线上 MySQL 建表脚本
直连 server/.env 中 MYSQL_ROOT_* 指向的线上 MySQL（默认 39.106.63.179），
在 ai_golden_vs_persian 库中执行 server/sql/schema.sql 建 hd_* 表。
"""
import asyncio
import os
from pathlib import Path

import asyncmy
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / "server" / ".env"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "server" / "sql" / "schema.sql"

load_dotenv(ENV_PATH)


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
    async with conn.cursor() as cur:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        for raw in sql.split(";"):
            # 剥离以 -- 开头的整行注释，再判断是否还有可执行 SQL
            lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
            stmt = "\n".join(lines).strip()
            if not stmt:
                continue
            print(f"[i] 执行: {stmt.splitlines()[0][:80]} ...")
            await cur.execute(stmt)
        await conn.commit()

        await cur.execute("SHOW TABLES LIKE 'hd_%'")
        rows = await cur.fetchall()
        print("[i] 线上已建 hd_* 表：", [r[0] for r in rows])
    await conn.ensure_closed()
    print("[✓] 线上初始化完成")


if __name__ == "__main__":
    asyncio.run(main())
