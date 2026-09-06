"""PNG → WebP 转换（启动提速 B 项）

把 front/public 下游戏资源转 WebP 并删除原 PNG（git 中保留历史）：
  - 道具图标（显示 ≤150px）同时缩放到 384px（原来 750px+）
  - 卡面/托盘保持原尺寸仅转编码

用法：
    python scripts/convert_webp.py --check      # 只列出仍为 .png 的命中文件
    python scripts/convert_webp.py              # 转换（默认在 front/public 下执行）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "front" / "public"
THEME_DIRS = sorted((PUBLIC / "images" / "game" / "cards" / "themes").glob("*"))
SPECIAL = [
    PUBLIC / "images" / "game" / "cards" / "slots.png",
    *sorted((PUBLIC / "images" / "game" / "props").glob("*.png")),
]

PROP_RESIZE = 384  # 道具图标目标边长（≈显示尺寸 2-3x，原图 750px+ 冗余）
QUALITY = 84       # 卡面/托盘质量；道具用 88（放大到边也更清晰）


def target_webp(png: Path) -> Path:
    return png.with_suffix(".webp")


def candidates() -> list[Path]:
    files = [p for p in SPECIAL if p.exists()]
    for d in THEME_DIRS:
        if d.is_dir():
            files += sorted(d.glob("*.png"))
    return [p for p in files if p.exists()]


def encode(png: Path) -> tuple[int, int]:
    im = Image.open(png).convert("RGBA")
    old_bytes = png.stat().st_size
    if png.parent.name == "props":
        side = PROP_RESIZE
        if max(im.size) > side:
            im = im.resize((side, side), Image.LANCZOS)
    dst = target_webp(png)
    im.save(dst, "WEBP", quality=QUALITY if png.parent.name == "props" else 82, method=4)
    return old_bytes, dst.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="仅列出待转换文件")
    args = parser.parse_args()

    files = candidates()
    if not files:
        print("[i] 无可转换的 PNG（已全部为 WebP？）")
        return 0

    if args.check:
        for f in files:
            print(f.relative_to(PUBLIC))
        print(f"[i] 共 {len(files)} 个待转换")
        return 0

    total_old = total_new = 0
    for idx, f in enumerate(files, 1):
        if target_webp(f).exists():
            # 已转换（含上次中断残留）：清理原 PNG 后跳过
            f.unlink(missing_ok=True)
            continue
        old, new = encode(f)
        total_old += old
        total_new += new
        f.unlink()
        print(f"[{idx:3d}/{len(files)}] {f.relative_to(PUBLIC)}  {old//1024}KB → {new//1024}KB")
    print(f"\n[✓] 完成：{total_old//1024}KB → {total_new//1024}KB（省 {(1 - total_new/total_old)*100:.0f}%）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
