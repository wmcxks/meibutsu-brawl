"""baseline: hd_* 全量结构（等价 schema.sql）

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-06

说明：
- 基线迁移逐条执行 server/sql/schema.sql 的 DDL（CREATE TABLE IF NOT EXISTS），
  对「已用手工 001~008 迁移的老库」执行是幂等 no-op，可放心 upgrade head 后 stamp。
- 自本基线之后的结构变更一律写 alembic revision（python -m alembic revision --autogenerate -m "..."），
  不再新增 sql/migrations/00X 手工文件。
"""

from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

_SCHEMA_SQL = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"


def _split_statements(sql: str) -> list[str]:
    """按分号拆分并剥离 -- 整行注释（与 scripts/migrate_remote.py 同规则）"""
    stmts = []
    for raw in sql.split(";"):
        lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            stmts.append(stmt)
    return stmts


def upgrade() -> None:
    sql = _SCHEMA_SQL.read_text(encoding="utf-8")
    for stmt in _split_statements(sql):
        op.execute(stmt)


def downgrade() -> None:
    # 基线不做 DROP：防误删线上数据。需要回滚时请手动生成 DROP 迁移。
    pass
