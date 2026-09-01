"""
OSS 批量上传脚本

用途：把 client/images 下所有图片同步到阿里云 OSS，并生成前端可用的 URL 清单。

用法（在本目录下执行）：
    uv sync                              # 首次安装依赖
    uv run python upload.py              # 增量上传（默认，基于 MD5/ETag 比对）
    uv run python upload.py --dry-run    # 仅打印待传列表，不实际上传
    uv run python upload.py --force      # 全量覆盖

配置：复用 server/.env 的 OSS_* 变量。
对象键格式：v1/images/<相对路径>   例如  v1/images/game/cards/animals/1.png
清单输出：client/oss_manifest.json   键为本地相对 client/images 的 POSIX 路径
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Iterator

import oss2
from dotenv import load_dotenv

# ──────────────── 路径与常量 ────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent                # scripts/oss_upload → 项目根
SERVER_ENV = PROJECT_ROOT / "server" / ".env"
LOCAL_ROOT = PROJECT_ROOT / "client" / "images"
MANIFEST_OUT = PROJECT_ROOT / "client" / "oss_manifest.json"

OSS_PREFIX = "v1/images"                               # OSS 对象键前缀（版本化）
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


# ──────────────── 工具函数 ────────────────
def load_oss_config() -> dict[str, str]:
    if not SERVER_ENV.exists():
        sys.exit(f"[x] 找不到配置文件: {SERVER_ENV}")
    load_dotenv(SERVER_ENV)
    required = ["OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET",
                "OSS_BUCKET_NAME", "OSS_ENDPOINT"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        sys.exit(f"[x] .env 缺少配置: {', '.join(missing)}")
    return {k: os.getenv(k) for k in required}


def iter_local_images() -> Iterator[Path]:
    if not LOCAL_ROOT.exists():
        sys.exit(f"[x] 本地图片目录不存在: {LOCAL_ROOT}")
    for p in LOCAL_ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXT:
            yield p


def local_md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def oss_key_for(local: Path) -> str:
    rel = local.relative_to(LOCAL_ROOT).as_posix()     # 跨平台统一用 /
    return f"{OSS_PREFIX}/{rel}"


def public_url(endpoint: str, bucket: str, key: str) -> str:
    host = endpoint.replace("https://", "").replace("http://", "").rstrip("/")
    return f"https://{bucket}.{host}/{key}"


def remote_etag(bucket: oss2.Bucket, key: str) -> str | None:
    """查询 OSS 对象 ETag（不存在返回 None，存在返回小写 md5 hex）。"""
    try:
        meta = bucket.head_object(key)
        return meta.etag.strip('"').lower()
    except oss2.exceptions.NoSuchKey:
        return None


# ──────────────── 主流程 ────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="批量上传 client/images 到 OSS")
    parser.add_argument("--dry-run", action="store_true", help="仅打印待上传列表，不实际上传")
    parser.add_argument("--force", action="store_true", help="全量覆盖（跳过 MD5 比对）")
    args = parser.parse_args()

    cfg = load_oss_config()
    auth = oss2.Auth(cfg["OSS_ACCESS_KEY_ID"], cfg["OSS_ACCESS_KEY_SECRET"])
    bucket = oss2.Bucket(auth, cfg["OSS_ENDPOINT"], cfg["OSS_BUCKET_NAME"])

    files = sorted(iter_local_images())
    total = len(files)
    print(f"[i] 扫描到本地图片 {total} 张")
    print(f"[i] OSS: bucket={cfg['OSS_BUCKET_NAME']}  prefix={OSS_PREFIX}/")

    uploaded, skipped, failed = 0, 0, 0
    manifest: dict[str, str] = {}

    for idx, local in enumerate(files, 1):
        key = oss_key_for(local)
        rel = local.relative_to(LOCAL_ROOT).as_posix()
        manifest[rel] = public_url(cfg["OSS_ENDPOINT"], cfg["OSS_BUCKET_NAME"], key)

        # 增量判断
        need_upload = True
        if not args.force:
            if remote_etag(bucket, key) == local_md5(local):
                need_upload = False

        tag = "UP" if need_upload else "=="
        print(f"[{idx:3d}/{total}] [{tag}] {rel}")

        if not need_upload:
            skipped += 1
            continue

        if args.dry_run:
            uploaded += 1
            continue

        try:
            bucket.put_object_from_file(key, str(local))
            uploaded += 1
        except Exception as e:
            print(f"          [x] 失败: {e}")
            failed += 1

    # 写清单（dry-run 不写，避免误导）
    if not args.dry_run:
        MANIFEST_OUT.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"[i] URL 清单已写入: {MANIFEST_OUT.relative_to(PROJECT_ROOT)}")

    mode = "dry-run" if args.dry_run else ("force" if args.force else "incremental")
    label = "计划上传" if args.dry_run else "已上传"
    print(f"\n[✓] 模式: {mode}  |  {label}: {uploaded}  跳过: {skipped}  失败: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
