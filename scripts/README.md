# 运维脚本手册

## 一键发布 H5（H3）

```bash
# 本地
./scripts/deploy_web.sh v0.1.0
# 提供 ADMIN_BASE_URL + ADMIN_TOKEN 环境变量时，自动把 app.latest_url 指向新版 index.html
ADMIN_BASE_URL=http://<host>:8089 ADMIN_TOKEN=<token> ./scripts/deploy_web.sh v0.1.0

# LINE 平台发布（需先配 VITE_LIFF_ID）
VITE_TARGET_PLATFORM=line VITE_LIFF_ID=<liff-id> ./scripts/deploy_web.sh v0.1.0
```

CI：GitHub Actions `.github/workflows/ci.yml`
- push/PR 自动跑 server 编译+单测、client 构建
- 手动 `workflow_dispatch`（版本号必填）走同一发布逻辑，
  需要配置 Secrets：`OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET / OSS_BUCKET_NAME / OSS_ENDPOINT`，
  可选 `ADMIN_BASE_URL / ADMIN_TOKEN / VITE_LIFF_ID`。

## 健康巡检（F3，cron 友好）

```bash
# 每 5 分钟跑一次，失败（非 0）由告警网关处理
python scripts/ops_check.py --base http://<host>:8089 --token <ADMIN_TOKEN>
python scripts/ops_check.py --base http://<host>:8089 --token <ADMIN_TOKEN> --json   # 机器可读
```

cron 示例：`*/5 * * * * cd <repo> && python3 scripts/ops_check.py --json >> /var/log/hd_ops.log`

## 热点接口压测（H4）

```bash
python scripts/bench_load.py --base http://localhost:8089 --users 20 --seconds 30
```

> ⚠️ 只在联调/staging 环境执行：submit 会真实落库。
> 当前开发机 `server/.env` 的 MYSQL_* 指向线上 Aiven，切勿直接拿线上库跑基准。
> 压测账号会以 `bench-*` guest 身份产生记录；上线前建议清库或换隔离库。

## 数据库迁移

```bash
python scripts/migrate_remote.py                     # 老库手工迁移 001~008（幂等）
cd server && python -m alembic upgrade head          # 新结构一律走 alembic
```
