"""本地 MySQL 连接测试 + 执行 server/sql/schema.sql 建表"""
import asyncio
import os
from pathlib import Path

import asyncmy
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / "server" / ".env"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "server" / "sql" / "schema.sql"

load_dotenv(ENV_PATH)


async def main():
    host = os.environ["MYSQL_HOST"]
    port = int(os.environ["MYSQL_PORT"])
    user = os.environ["MYSQL_USER"]
    password = os.environ["MYSQL_PASSWORD"]
    db = os.environ["MYSQL_DATABASE"]

    print(f"[i] 连接 MySQL {user}@{host}:{port}/{db} ...")
    conn = await asyncmy.connect(
        host=host, port=port, user=user, password=password, db=db, charset="utf8mb4"
    )
    async with conn.cursor() as cur:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        # asyncmy execute 不支持多语句，拆分执行
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
        print("[i] 已建 hd_* 表：", [r[0] for r in rows])
    await conn.ensure_closed()
    print("[✓] 初始化完成")


if __name__ == "__main__":
    asyncio.run(main())
