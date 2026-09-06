# OSS 上传脚本

复用 `server/.env` 的 `OSS_*` 配置。首次运行：`uv sync`。

## 前端静态资源（H3：CDN 化）

```bash
# 1) 构建（注入 CDN base + 版本号）
cd ../../front
VITE_APP_VERSION=v0.1.0 \
VITE_CDN_BASE=https://<bucket>.<endpoint-host>/h5/v0.1.0/ \
npm run build:cdn

# 2) 上传 dist 到 OSS h5/v0.1.0/（增量；--dry-run 预览 / --force 覆盖）
cd ../scripts/oss_upload
uv run python upload_web.py --version v0.1.0
```

- 产物带内容哈希 → 长缓存（Cache-Control: immutable）；index.html 无缓存
- 上传后写 `h5/latest.json`（版本/资源清单，供部署与回滚脚本）
- 强更：后台把配置 `app.latest_url` 设为 `https://<bucket>.<host>/h5/v0.1.0/index.html`
- index.html 建议部署在正式域名（Nginx/静态站），通过 latest 指最新版本目录

## 图片/音频批量同步（旧 client 目录）

```bash
uv run python upload.py            # 增量（MD5 比对）
uv run python upload.py --force    # 全量覆盖
uv run python upload_audio.py      # 音频
```
