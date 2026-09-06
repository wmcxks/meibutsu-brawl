# Alembic 迁移（H1）

从手工 `server/sql/migrations/00X_*.sql` 切换为 Alembic。基线迁移
`versions/0001_baseline.py` 等价于当前 `schema.sql`（逐条 CREATE IF NOT EXISTS），
老库执行是幂等 no-op。

## 常用命令（必须在 server/ 目录执行，读 server/.env 的 MYSQL_*）

```bash
# 迁移到最新（老库 = no-op，之后自动 stamp）
python -m alembic upgrade head

# 预览将要执行的 SQL（不连库）
python -m alembic upgrade head --sql

# 生成新迁移（对比 ORM metadata 与当前库差异，产出后务必人工审查）
python -m alembic revision --autogenerate -m "描述"

# 查看版本链 / 当前版本
python -m alembic history --verbose
python -m alembic current
```

> 运行解释器用项目依赖 venv（`../scripts/venv/bin/python`），依赖见 `server/pyproject.toml`。

## 约定

1. 基线之前的手工迁移（001~008）保留供老库参考，**不再新增**；后续结构变更
   一律 `alembic revision --autogenerate`（自审 ALTER/索引后提交）。
2. 种子数据（配置/任务/关卡/装扮目录）仍可写进迁移的 upgrade()，
   老库中已手工执行过的种子用 INSERT IGNORE / 幂等写法避免重复。
3. downgrade 迁移只用于开发环境；生产回滚走「新迁移反向修复」，严禁 DROP 数据。
