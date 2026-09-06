"""
H5 构建产物 OSS 上传脚本（H3：静态资源 CDN 化）

用途：把 front/dist（vite build 产物，文件已带内容哈希）同步到阿里云 OSS，
      index.html 走无缓存，其余带哈希资源长缓存。

用法（在本目录下执行）：
    uv sync
    uv run python upload_web.py --version v0.1.0            # 上传到 h5/v0.1.0/，并生成 latest 清单
    uv run python upload_web.py --version v0.1.0 --dry-run  # 仅打印
    uv run python upload_web.py --version v0.1.0 --force    # 全量覆盖

配套：
    1) 构建：cd front && VITE_APP_VERSION=v0.1.0 VITE_CDN_BASE=https://<bucket>.oss-.../<prefix>/ npm run build:cdn
    2) 强更：把 app.latest_url 配置成 https://<bucket>.oss-.../<prefix>/index.html（运营后台 /api/admin/configs）
    3) index.html 部署到后端同域（Nginx）或任意静态站点，通过 latest 指到新版本目录
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import oss2
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SERVER_ENV = PROJECT_ROOT / "server" / ".env"
DIST_DIR = PROJECT_ROOT / "front" / "dist"

OSS_PREFIX = "h5"                    # H5 资源版本化前缀 h5/<version>/
LATEST_MANIFEST_KEY = "h5/latest.json"
LONG_CACHE_EXT = {".js", ".css", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".woff2", ".mp3", ".ogg"}
HTML_EXT = {".html"}


def load_oss_config() -> dict[str, str]:
    if not SERVER_ENV.exists():
        sys.exit(f"[x] 找不到配置文件: {SERVER_ENV}")
    load_dotenv(SERVER_ENV)
    required = ["OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET", "OSS_BUCKET_NAME", "OSS_ENDPOINT"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        sys.exit(f"[x] .env 缺少配置: {', '.join(missing)}")
    return {k: os.getenv(k) for k in required}


def local_md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def cache_control_for(key: str) -> str:
    """带哈希资源长缓存；index.html 等 html 无缓存（配合最新版本目录跳转）"""
    if Path(key).suffix.lower() in LONG_CACHE_EXT:
        return "public, max-age=31536000, immutable"
    if Path(key).suffix.lower() in HTML_EXT or key.endswith(".json"):
        return "no-cache"
    return "public, max-age=86400"


def main() -> int:
    parser = argparse.ArgumentParser(description="上传 front/dist 到 OSS（H3 CDN）")
    parser.add_argument("--version", required=True, help="版本号（如 v0.1.0），作为 OSS 目录前缀")
    parser.add_argument("--dry-run", action="store_true", help="仅打印待上传列表")
    parser.add_argument("--force", action="store_true", help="全量覆盖（跳过 MD5 比对）")
    args = parser.parse_args()

    ver = args.version.lstrip("v")
    if not DIST_DIR.exists():
        sys.exit(f"[x] 找不到构建产物目录（请先 cd front && npm run build:cdn）: {DIST_DIR}")
    if "--" in ver or ver.startswith("."):
        sys.exit("[x] 非法版本号")

    cfg = load_oss_config()
    auth = oss2.Auth(cfg["OSS_ACCESS_KEY_ID"], cfg["OSS_ACCESS_KEY_SECRET"])
    bucket = oss2.Bucket(auth, cfg["OSS_ENDPOINT"], cfg["OSS_BUCKET_NAME"])
    prefix = f"{OSS_PREFIX}/v{ver}"

    files = sorted(p for p in DIST_DIR.rglob("*") if p.is_file())
    print(f"[i] 扫描到构建产物 {len(files)} 个")
    print(f"[i] OSS: bucket={cfg['OSS_BUCKET_NAME']}  prefix={prefix}/")

    uploaded, skipped, failed = 0, 0, 0
    entries: dict[str, str] = {}

    for idx, local in enumerate(files, 1):
        rel = local.relative_to(DIST_DIR).as_posix()
        key = f"{prefix}/{rel}"
        entries[rel] = key

        need_upload = True
        if not args.force:
            try:
                meta = bucket.head_object(key)
                if meta.etag.strip('"').lower() == local_md5(local):
                    need_upload = False
            except oss2.exceptions.NoSuchKey:
                pass

        tag = "UP" if need_upload else "=="
        print(f"[{idx:3d}/{len(files)}] [{tag}] {rel}")

        if not need_upload:
            skipped += 1
            continue
        if args.dry_run:
            uploaded += 1
            continue

        try:
            headers = {"Cache-Control": cache_control_for(key)}
            content_type = None
            if Path(rel).suffix.lower() == ".html":
                content_type = "text/html; charset=utf-8"
            bucket.put_object_from_file(key, str(local), headers=headers)
            if content_type:
                bucket.update_object_meta(key, {"Content-Type": content_type})
            uploaded += 1
        except Exception as e:
            print(f"          [x] 失败: {e}")
            failed += 1

    if not args.dry_run:
        # latest 清单：记录最新版本与资源键（供部署/回滚脚本读取）
        latest = {"version": f"v{ver}", "base": f"{prefix}/", "files": entries}
        bucket.put_object(
            LATEST_MANIFEST_KEY,
            json.dumps(latest, ensure_ascii=False, indent=2, sort_keys=True),
            headers={"Cache-Control": "no-cache", "Content-Type": "application/json"},
        )
        print(f"[i] 版本清单已写入: {LATEST_MANIFEST_KEY}")

    label = "计划上传" if args.dry_run else "已上传"
    mode = "dry-run" if args.dry_run else ("force" if args.force else "incremental")
    print(f"\n[✓] 模式: {mode}  |  {label}: {uploaded}  跳过: {skipped}  失败: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
