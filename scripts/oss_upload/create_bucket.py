"""
创建阿里云 OSS Bucket（一次性脚本）

用途：用代码快速创建一个新 bucket，自动设为公共读，省去控制台点击。
读取 server/.env 里的 OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET 作为凭证。

用法（在本目录下执行）：
    uv run python create_bucket.py --name yanglegeyang-assets
    uv run python create_bucket.py --name my-bucket --region cn-hangzhou
    uv run python create_bucket.py --name my-bucket --acl private        # 改成私有读写

参数：
    --name    Bucket 名称（全局唯一，3-63 字符，小写字母/数字/短横线）
    --region  地域，默认 cn-shanghai；可选 cn-hangzhou / cn-beijing / cn-shenzhen 等
    --acl     读写权限，默认 public-read；可选 private / public-read-write

成功后会打印需要更新到 server/.env 的两行配置。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import oss2
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SERVER_ENV = PROJECT_ROOT / "server" / ".env"

ACL_MAP = {
    "private": oss2.BUCKET_ACL_PRIVATE,
    "public-read": oss2.BUCKET_ACL_PUBLIC_READ,
    "public-read-write": oss2.BUCKET_ACL_PUBLIC_READ_WRITE,
}


def load_credentials() -> tuple[str, str]:
    if not SERVER_ENV.exists():
        sys.exit(f"[x] 找不到配置文件: {SERVER_ENV}")
    load_dotenv(SERVER_ENV)
    ak = os.getenv("OSS_ACCESS_KEY_ID")
    sk = os.getenv("OSS_ACCESS_KEY_SECRET")
    if not ak or not sk:
        sys.exit("[x] .env 中缺少 OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET")
    return ak, sk


def validate_bucket_name(name: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]", name):
        sys.exit(f"[x] bucket 名不合法: {name}（需 3-63 位，小写字母/数字/短横线，不以横线开头结尾）")


def main() -> int:
    parser = argparse.ArgumentParser(description="创建阿里云 OSS Bucket")
    parser.add_argument("--name", required=True, help="Bucket 名称（全局唯一）")
    parser.add_argument("--region", default="cn-shanghai",
                        help="地域，默认 cn-shanghai（如 cn-hangzhou / cn-beijing）")
    parser.add_argument("--acl", default="public-read", choices=list(ACL_MAP.keys()),
                        help="读写权限，默认 public-read")
    args = parser.parse_args()

    validate_bucket_name(args.name)
    ak, sk = load_credentials()

    endpoint = f"https://oss-{args.region}.aliyuncs.com/"
    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, endpoint, args.name)

    print(f"[i] 准备创建 bucket: {args.name}")
    print(f"[i] 地域: {args.region}   权限: {args.acl}   endpoint: {endpoint}")

    try:
        bucket.create_bucket(ACL_MAP[args.acl])
    except oss2.exceptions.ServerError as e:
        if e.code == "BucketAlreadyExists":
            sys.exit(f"[x] 该 bucket 名已被他人占用，请换一个: {args.name}")
        if e.code == "BucketAlreadyOwnedByYou":
            print(f"[!] 你已拥有同名 bucket，继续用现有的: {args.name}")
        else:
            sys.exit(f"[x] 创建失败: {e.code} - {e.message}")
    except Exception as e:
        sys.exit(f"[x] 创建失败: {e}")
    else:
        print(f"[✓] 创建成功")

    # 校验 + 打印配置
    try:
        info = bucket.get_bucket_info()
        print(f"[i] Bucket 名: {info.name}")
        print(f"[i] 创建时间: {info.creation_date}")
        print(f"[i] 读写权限: {info.acl.grant}")
    except Exception as e:
        print(f"[!] 获取信息失败（不影响使用）: {e}")

    print("\n" + "=" * 60)
    print("请把下面两行更新到 server/.env：")
    print("=" * 60)
    print(f"OSS_BUCKET_NAME={args.name}")
    print(f"OSS_ENDPOINT={endpoint}")
    print("=" * 60)
    print("\n下一步：")
    print(f"    uv run python upload.py --force   # 把 client/images 全量传到新 bucket")
    return 0


if __name__ == "__main__":
    sys.exit(main())
