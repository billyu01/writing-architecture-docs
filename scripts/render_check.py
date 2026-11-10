#!/usr/bin/env python3
"""无头浏览器截图，用于配图的视觉终检（可选依赖，找不到浏览器时给出明确提示）。

用法：
  python3 render_check.py <html文件> [--outdir /tmp/fig-check] [--widths 1720,900] [--height 2400]

依赖：本机已安装 Chrome / Chromium / Edge 之一；可选 Pillow（用于按非白区域自动裁剪底部留白）。
找不到浏览器时退出码 2，并打印手动检查清单——不静默假装通过。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

CANDIDATES = [
    os.environ.get("CHROME_PATH", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def find_browser() -> str | None:
    for cand in CANDIDATES:
        if cand and Path(cand).exists():
            return cand
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def trim_bottom(path: Path) -> None:
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return
    try:
        img = Image.open(path).convert("RGB")
        w, h = img.size
        pixels = img.load()
        bottom = 0
        for y in range(h - 1, -1, -1):
            row_blank = True
            for x in range(0, w, max(1, w // 120)):
                r, g, b = pixels[x, y]
                if not (r > 245 and g > 245 and b > 245):
                    row_blank = False
                    break
            if not row_blank:
                bottom = y
                break
        if 0 < bottom < h - 1:
            img.crop((0, 0, w, min(h, bottom + 24))).save(path)
    except Exception:
        return


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="配图无头浏览器截图")
    parser.add_argument("html", help="待检查的 HTML 文件")
    parser.add_argument("--outdir", default="/tmp/arch-figure-check", help="截图输出目录")
    parser.add_argument("--widths", default="1720,900", help="逗号分隔的视口宽度")
    parser.add_argument("--height", type=int, default=2400, help="视口高度（默认 2400）")
    args = parser.parse_args(argv)

    html = Path(args.html).resolve()
    if not html.exists():
        print(f"文件不存在：{html}", file=sys.stderr)
        return 2

    browser = find_browser()
    if browser is None:
        print("未找到 Chrome/Chromium/Edge。请手动完成视觉终检：", file=sys.stderr)
        print("  1) 浏览器打开文件，按目标宽度截图（整图）；")
        print("  2) 按分区/图例/最长标签裁剪放大；")
        print("  3) 缩到 900px 宽再截一次，确认无横向滚动、文字未压扁；")
        print("  4) 把结论写进评审记录。", file=sys.stderr)
        return 2

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    widths = [int(w) for w in args.widths.split(",") if w.strip()]
    outputs: list[Path] = []
    for width in widths:
        out = outdir / f"{html.stem}-{width}w.png"
        profile_dir = outdir / "chrome-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-sandbox",
            "--no-first-run",
            "--disable-dev-shm-usage",
            f"--user-data-dir={profile_dir}",
            f"--window-size={width},{args.height}",
            "--virtual-time-budget=3000",
            f"--screenshot={out}",
            html.as_uri(),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not out.exists():
            print(f"[ERROR] {width}px 截图失败：{proc.stderr.strip()[:300]}", file=sys.stderr)
            return 1
        trim_bottom(out)
        outputs.append(out)
        print(f"[OK] {out}")

    print(f"共 {len(outputs)} 张截图。请人工确认：无空白/缺图、无重叠、无裁切、窄屏无横向滚动。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
