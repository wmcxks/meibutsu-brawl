"""
修复 OSS Bucket 的"阻止公共访问"开关 + 重设 ACL 为 public-read

阿里云新建 bucket 默认开启"阻止公共访问"（Block Public Access），即使 ACL 设了
public-read 也会返回 403。此脚本关闭该开关并确认 ACL。

用法：
    uv run python fix_bucket_acl.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import oss2
from dotenv import load_dotenv

SERVER_ENV = Path(__file__).resolve().parent.parent.parent / "server" / ".env"


def main() -> int:
    if not SERVER_ENV.exists():
        sys.exit(f"[x] 找不到配置: {SERVER_ENV}")
    load_dotenv(SERVER_ENV)

    ak = os.getenv("OSS_ACCESS_KEY_ID")
    sk = os.getenv("OSS_ACCESS_KEY_SECRET")
    bucket_name = os.getenv("OSS_BUCKET_NAME")
    endpoint = os.getenv("OSS_ENDPOINT")

    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    # 1. 关闭"阻止公共访问"
    print(f"[i] 操作 bucket: {bucket_name}")
    try:
        bucket.put_bucket_public_access_block(False)
        print("[✓] 已关闭『阻止公共访问』(BlockPublicAccess=False)")
    except Exception as e:
        print(f"[!] 关闭 BlockPublicAccess 失败（可能 SDK 版本不支持，需控制台关）: {e}")

    # 2. 确认 ACL 为 public-read
    try:
        bucket.put_bucket_acl(oss2.BUCKET_ACL_PUBLIC_READ)
        print("[✓] ACL 已设为 public-read")
    except Exception as e:
        sys.exit(f"[x] 设置 ACL 失败: {e}")

    # 3. 检查当前状态
    try:
        acl = bucket.get_bucket_acl()
        print(f"[i] 当前 ACL: {acl.acl}")
    except Exception:
        pass

    try:
        status = bucket.get_bucket_public_access_block()
        print(f"[i] 当前 BlockPublicAccess: {status.block_public_access}")
    except Exception as e:
        print(f"[!] 查询 BlockPublicAccess 失败: {e}")

    print("\n[✓] 修复完成，请刷新页面重试。")
    print("    验证：浏览器打开以下 URL 应显示图片：")
    print(f"    https://{bucket_name}.{endpoint.replace('https://','').rstrip('/')}/v1/images/menu/titles/title.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
