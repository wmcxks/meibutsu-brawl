#!/usr/bin/env bash
# ============================================================
# 一键发布 H5（H3）：build → OSS 上传 → 更新 latest_url 强更入口
#
# 用法（仓库根目录执行）：
#   ./scripts/deploy_web.sh v0.1.0                # 常规发布
#   ./scripts/deploy_web.sh v0.1.0 --skip-upload   # 只构建不传 OSS
#   ADMIN_BASE_URL=http://<server>:8089 ADMIN_TOKEN=xxx ./scripts/deploy_web.sh v0.1.0
#
# 环境变量（可选）：
#   VITE_TARGET_PLATFORM  目标平台 web|line（默认 web，line 还需 VITE_LIFF_ID）
#   ADMIN_BASE_URL        后端地址；与 ADMIN_TOKEN 同时提供时自动把
#                         app.latest_url 配置为新版 index.html（强更跳转）
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
SERVER_ENV="$ROOT/server/.env"
FRONT_DIR="$ROOT/front"
OSS_DIR="$ROOT/scripts/oss_upload"

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "[x] 用法: $0 v<版本号> [--skip-upload]" >&2
  exit 1
fi
VER="${VERSION#v}"
SKIP_UPLOAD=0
[[ "${2:-}" == "--skip-upload" ]] && SKIP_UPLOAD=1

[[ -f "$SERVER_ENV" ]] || { echo "[x] 缺少 $SERVER_ENV" >&2; exit 1; }

# ── 从 server/.env 取 OSS 配置（只读值） ──────────────────────────
read_oss_env() {
  python3 - "$1" <<'PY'
import sys
key = sys.argv[1]
for line in open("server/.env", encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        if k == key:
            print(v.strip())
            return
sys.exit(1)
PY
}
OSS_BUCKET="$(read_oss_env OSS_BUCKET_NAME)"
OSS_ENDPOINT="$(read_oss_env OSS_ENDPOINT)"

if [[ -z "$OSS_BUCKET" || -z "$OSS_ENDPOINT" ]]; then
  echo "[x] server/.env 缺少 OSS_BUCKET_NAME / OSS_ENDPOINT" >&2
  exit 1
fi

HOST="${OSS_ENDPOINT#https://}"
HOST="${HOST#http://}"
HOST="${HOST%/}"
CDN_BASE="https://${OSS_BUCKET}.${HOST}/h5/v${VER}/"

echo "[1/3] 构建 front (VITE_APP_VERSION=v${VER} VITE_CDN_BASE=${CDN_BASE})"
(cd "$FRONT_DIR" && VITE_APP_VERSION="v${VER}" VITE_CDN_BASE="$CDN_BASE" npm run build:cdn)

if [[ "$SKIP_UPLOAD" == "1" ]]; then
  echo "[2/3] 跳过 OSS 上传（--skip-upload）"
else
  echo "[2/3] 上传到 OSS h5/v${VER}/"
  if command -v uv >/dev/null 2>&1; then
    (cd "$OSS_DIR" && uv run python upload_web.py --version "v${VER}")
  else
    echo "[i] 未检测到 uv，改用 python3 + pip 安装上传依赖"
    (cd "$OSS_DIR" && python3 -m pip install -q oss2 python-dotenv && python3 upload_web.py --version "v${VER}")
  fi
fi

INDEX_URL="${CDN_BASE}index.html"

# ── 可选：更新强更入口 latest_url（管理后台配置） ──────────────────
if [[ -n "${ADMIN_BASE_URL:-}" && -n "${ADMIN_TOKEN:-}" ]]; then
  echo "[3/3] 配置 app.latest_url = ${INDEX_URL}"
  curl -fsS -X PUT "${ADMIN_BASE_URL%/}/api/admin/configs/app.latest_url" \
    -H "X-Admin-Token: ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"value\": \"${INDEX_URL}\", \"remark\": \"deploy ${VERSION}\"}" >/dev/null
else
  echo "[3/3] 跳过 latest_url 配置（未提供 ADMIN_BASE_URL / ADMIN_TOKEN）"
fi

echo ""
echo "[✓] 发布完成: v${VER}"
echo "    index.html → ${INDEX_URL}"
