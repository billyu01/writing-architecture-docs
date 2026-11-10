#!/usr/bin/env python3
"""把多张 SVG 内联进架构 HTML 模板，并统一给 id / class 加前缀（只依赖标准库）。

为什么需要它：
  1. 架构文档的 HTML 可视版必须「内联 SVG」，不能 iframe（iframe 会出滚动条、被裁切、打印丢失）；
  2. 多张 SVG 内联到同一页面时，marker / title / desc / 样式 class 会重名，后图样式会污染前图；
  3. 手工内联不可重复、不可审查。这个脚本让「模板 + SVG 资产 + 一张清单」可以一键重建。

用法：
  python3 embed_svg.py --manifest figures.json [--check]

清单格式（JSON）：
  {
    "template": "docs/architecture/architecture.html.template",
    "output": "docs/architecture/architecture.html",
    "figures": [
      {"slug": "domain-model", "svg": "docs/architecture/assets/domain-model.svg"},
      {"slug": "deployment",   "svg": "docs/architecture/assets/deployment.svg"}
    ]
  }

模板里用注释占位：<!--INLINE:domain-model-->，脚本替换为处理后的 <svg>。
路径相对当前工作目录解析。

命名规则：加前缀后的 id/class 形如 <slug>--<原名>。分隔符用 --，避免与常见命名冲突。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ID_ATTR_RE = re.compile(r'\bid="([^"]+)"')
CLASS_ATTR_RE = re.compile(r'\bclass="([^"]+)"')
CLASS_SELECTOR_RE = re.compile(r"\.([A-Za-z_][A-Za-z0-9_-]*)")
STYLE_BLOCK_RE = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.S | re.I)
URL_REF_RE = re.compile(r"url\(\s*#([^)\s]+)\s*\)")
HREF_REF_RE = re.compile(r'((?:xlink:)?href)="#([^"]+)"')
ARIA_LABELLEDBY_RE = re.compile(r'(aria-labelledby=")([^"]+)(")')
PLACEHOLDER_RE = re.compile(r"<!--\s*INLINE:([A-Za-z0-9_-]+)\s*-->")
SVG_ROOT_RE = re.compile(r"<svg\b", re.I)
SVG_ROLE_RE = re.compile(r'role="img"', re.I)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def collect_prefixes(svg: str) -> tuple[set[str], set[str]]:
    ids = set(ID_ATTR_RE.findall(svg))
    classes: set[str] = set()
    for _, style, _ in STYLE_BLOCK_RE.findall(svg):
        classes |= set(CLASS_SELECTOR_RE.findall(style))
    return ids, classes


def prefix_svg(svg: str, slug: str) -> str:
    ids, classes = collect_prefixes(svg)
    prefix = f"{slug}--"

    def rewrite_style(m: re.Match[str]) -> str:
        head, style, tail = m.group(1), m.group(2), m.group(3)
        for cls in classes:
            style = re.sub(r"(?<![\w-])\." + re.escape(cls) + r"(?![\w-])", "." + prefix + cls, style)
        for ident in ids:
            style = re.sub(r"(?<![\w-])#" + re.escape(ident) + r"(?![\w-])", "#" + prefix + ident, style)
        return head + style + tail

    svg = STYLE_BLOCK_RE.sub(rewrite_style, svg)

    for ident in ids:
        svg = re.sub(r'\bid="' + re.escape(ident) + r'"', f'id="{prefix}{ident}"', svg)
    for ident in ids:
        svg = svg.replace(f"url(#{ident})", f"url(#{prefix}{ident})")
        svg = HREF_REF_RE.sub(lambda m: f'{m.group(1)}="#{prefix}{m.group(2)}"' if m.group(2) in ids else m.group(0), svg)
    svg = ARIA_LABELLEDBY_RE.sub(
        lambda m: m.group(1) + " ".join(prefix + t if t in ids else t for t in m.group(2).split()) + m.group(3),
        svg,
    )

    def rewrite_class_attr(m: re.Match[str]) -> str:
        tokens = [prefix + t if t in classes else t for t in m.group(1).split()]
        return 'class="' + " ".join(tokens) + '"'

    svg = CLASS_ATTR_RE.sub(rewrite_class_attr, svg)
    return svg


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="把 SVG 内联进架构 HTML 模板")
    parser.add_argument("--manifest", required=True, help="内联清单 JSON 路径")
    parser.add_argument("--check", action="store_true", help="只校验，不写输出文件")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(f"清单不存在：{manifest_path}", file=sys.stderr)
        return 2
    try:
        manifest = json.loads(read_text(manifest_path))
    except json.JSONDecodeError as exc:
        print(f"清单不是合法 JSON：{exc}", file=sys.stderr)
        return 2

    base = manifest_path.parent
    template = (base / manifest["template"]).resolve() if not Path(manifest["template"]).is_absolute() else Path(manifest["template"])
    output = (base / manifest["output"]).resolve() if not Path(manifest["output"]).is_absolute() else Path(manifest["output"])
    figures = manifest.get("figures", [])

    if not template.exists():
        print(f"模板不存在：{template}", file=sys.stderr)
        return 2
    html = read_text(template)
    errors: list[str] = []
    warnings: list[str] = []

    for fig in figures:
        slug = fig.get("slug", "")
        svg_path = base / fig.get("svg", "")
        if not slug or not svg_path.exists():
            errors.append(f"图 {slug or '(无 slug)'} 的 SVG 不存在：{svg_path}")
            continue
        svg = read_text(svg_path)
        if not SVG_ROOT_RE.search(svg):
            errors.append(f"图 {slug} 的文件里没有 <svg>：{svg_path}")
            continue
        if not SVG_ROLE_RE.search(svg):
            warnings.append(f"图 {slug} 的 <svg> 缺 role=\"img\"")
        placeholder = f"<!--INLINE:{slug}-->"
        if placeholder not in html:
            errors.append(f"模板缺少占位符 {placeholder}")
            continue
        html = html.replace(placeholder, prefix_svg(svg, slug))

    leftovers = PLACEHOLDER_RE.findall(html)
    if leftovers:
        warnings.append("模板仍残留占位符：" + "、".join(sorted(set(leftovers))))

    for line in errors:
        print(f"[ERROR] {line}")
    for line in warnings:
        print(f"[WARN] {line}")
    print(f"图 {len(figures)} 张，模板 {template.name}，输出 {output}")

    if errors:
        print("构建失败：先修占位符与图路径。", file=sys.stderr)
        return 1
    if args.check:
        print("校验通过（--check，未写文件）。")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    print(f"已写入 {output}（{len(html)} 字符）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
