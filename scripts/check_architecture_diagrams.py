#!/usr/bin/env python3
"""架构配图自检（只依赖 Python 标准库）。

用法：
  python3 check_architecture_diagrams.py <文件或目录>... [--strict]

检查对象：diagram-design 产出的自包含 HTML（内联 SVG），或裸 SVG 文件。

检查项：
  A. 可访问性契约：<svg role="img">、aria-labelledby、非空 <title>/<desc>
  B. 结构完整性：viewBox；id 在文档内唯一；多个内联 SVG 之间 id/class 不冲突
  C. 引用完整性：marker-end / fill="url(#x)" / href="#x" 的锚点存在
  D. 文字溢出（启发式）：按字号估算文本宽度，检查是否越出 viewBox；跨容器溢出需人工复核
  E. 页面整洁：iframe 残留、横向滚动样式、中文缺字体
  F. 连接器：疑似斜线/穿节点（启发式，warning）

退出码：0 = 没有 error；1 = 有 error；--strict 时 warning 也算失败。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"

SVG_BLOCK_RE = re.compile(r"<svg\b[^>]*>.*?</svg>", re.S | re.I)
STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.S | re.I)
ID_ATTR_RE = re.compile(r'\bid="([^"]+)"')
CLASS_ATTR_RE = re.compile(r'\bclass="([^"]+)"')
CLASS_SELECTOR_RE = re.compile(r"\.([A-Za-z_][A-Za-z0-9_-]*)")
URL_REF_RE = re.compile(r"url\(\s*#([^)\s]+)\s*\)")
HREF_ANCHOR_RE = re.compile(r'(?:xlink:)?href="#([^"]+)"')
TEXT_RE = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S | re.I)
ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')
RECT_RE = re.compile(r"<rect\b([^>]*)>", re.I)
PATH_RE = re.compile(r'<path\b([^>]*)>', re.I)
LINE_RE = re.compile(r'<line\b([^>]*)>', re.I)
IFRAME_RE = re.compile(r"<iframe\b", re.I)
CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


class Report:
    def __init__(self, strict: bool = False) -> None:
        self.rows: list[tuple[str, str, str, str]] = []
        self.strict = strict

    def add(self, level: str, path: str, check: str, message: str) -> None:
        self.rows.append((level, path, check, message))

    def error(self, path: str, check: str, message: str) -> None:
        self.add(ERROR, path, check, message)

    def warn(self, path: str, check: str, message: str) -> None:
        self.add(WARN, path, check, message)

    def info(self, path: str, check: str, message: str) -> None:
        self.add(INFO, path, check, message)

    def print(self) -> int:
        order = {ERROR: 0, WARN: 1, INFO: 2}
        for level, path, check, message in sorted(self.rows, key=lambda r: (order[r[0]], r[1], r[2])):
            print(f"[{level}] {path} :: {check} :: {message}")
        counts = {lvl: sum(1 for r in self.rows if r[0] == lvl) for lvl in (ERROR, WARN, INFO)}
        print()
        print(f"汇总：{counts[ERROR]} 个 error，{counts[WARN]} 个 warning，{counts[INFO]} 条提示。")
        if counts[ERROR]:
            return 1
        if self.strict and counts[WARN]:
            return 1
        return 0


def parse_attrs(attr_text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in ATTR_RE.finditer(attr_text)}

def collect_class_font_sizes(svg: str) -> dict[str, float]:
    sizes: dict[str, float] = {}
    for style in STYLE_BLOCK_RE.findall(svg):
        for m in re.finditer(r"\.([A-Za-z_][A-Za-z0-9_-]*)\s*\{([^}]*)\}", style):
            fs = re.search(r"font-size\s*:\s*([\d.]+)px", m.group(2))
            if fs:
                sizes[m.group(1)] = float(fs.group(1))
    return sizes


def collect_shapes(svg: str, view_w: float, view_h: float):
    """收集 rect 与 text 的包围盒（忽略 transform，按原始坐标近似比较）。"""
    rects = []
    for m in RECT_RE.finditer(svg):
        a = parse_attrs(m.group(1))
        try:
            x, y = float(a.get("x", 0)), float(a.get("y", 0))
            w, h = float(a.get("width", 0)), float(a.get("height", 0))
        except ValueError:
            continue
        if w <= 0 or h <= 0:
            continue
        if w >= view_w * 0.95 and h >= view_h * 0.95:
            continue  # 背景板
        rects.append({"x": x, "y": y, "w": w, "h": h})
    return rects


def collect_text_boxes(svg: str, class_font_sizes: dict[str, float] | None = None):
    boxes = []
    class_font_sizes = class_font_sizes or {}
    for m in TEXT_RE.finditer(svg):
        a = parse_attrs(m.group(1))
        content = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not content:
            continue
        try:
            x = float(a.get("x", "0"))
            y = float(a.get("y", "0"))
            inline_fs = a.get("font-size")
            if inline_fs:
                fs = float(re.sub(r"[^\d.]", "", inline_fs) or 12)
            else:
                fs = 12.0
                for cls in a.get("class", "").split():
                    if cls in class_font_sizes:
                        fs = class_font_sizes[cls]
                        break
        except ValueError:
            continue
        anchor = a.get("text-anchor", "start")
        width = text_width(content, fs)
        if anchor == "middle":
            left, right = x - width / 2, x + width / 2
        elif anchor == "end":
            left, right = x - width, x
        else:
            left, right = x, x + width
        boxes.append({"l": left, "r": right, "t": y - fs, "b": y + fs * 0.3, "fs": fs, "text": content})
    return boxes


def check_text_fit(svg: str, path: str, label: str, vw: float, vh: float, report: Report) -> None:
    rects = [r for r in collect_shapes(svg, vw, vh) if 40 <= r["w"] <= 400 and 20 <= r["h"] <= 300]
    if not rects:
        return
    for box in collect_text_boxes(svg, collect_class_font_sizes(svg)):
        cx = (box["l"] + box["r"]) / 2
        cy = (box["t"] + box["b"]) / 2
        cands = [r for r in rects if r["x"] <= cx <= r["x"] + r["w"] and r["y"] <= cy <= r["y"] + r["h"]]
        if not cands:
            continue
        host = min(cands, key=lambda r: r["w"] * r["h"])
        over = max(host["x"] - box["l"], box["r"] - (host["x"] + host["w"]))
        if over > 3:
            report.warn(path, "文字溢出", f"{label} 文字越出所属盒子：「{box['text'][:20]}」超出约 {over:.0f}px（盒宽 {host['w']:.0f}）")


def check_connector_endpoints(svg: str, path: str, label: str, vw: float, vh: float, report: Report) -> None:
    # 时序图的消息箭头连的是生命线/激活条，不是节点矩形；按图种跳过该项
    desc = re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.S)
    lifelines = re.findall(r'<line[^>]*stroke-dasharray="4,4"', svg)
    desc_text = desc.group(1) if desc else ""
    head = desc_text + re.search(r"<title[^>]*>(.*?)</title>", svg, re.S).group(1) if re.search(r"<title[^>]*>(.*?)</title>", svg, re.S) else desc_text
    if any(k in head for k in ("时序", "限界上下文", "领域模型", "进程视图", "开发视图")):
        return
    if len(lifelines) >= 3:
        return
    rects = collect_shapes(svg, vw, vh)
    node_rects = [r for r in rects if r["w"] >= 56 and r["h"] >= 28]
    if not node_rects:
        return
    hits = 0
    for m in PATH_RE.finditer(svg):
        attrs = parse_attrs(m.group(1))
        d = attrs.get("d", "")
        segments = straight_segments(d)
        if not segments:
            continue
        if not re.search(r"marker-end|marker-start", m.group(1)) and not attrs.get("stroke-dasharray"):
            continue
        endpoints = [(segments[0][0], segments[0][1]), (segments[-1][2], segments[-1][3])]
        for px, py in endpoints:
            on_edge = False
            for r in node_rects:
                x, y, w, h = r["x"], r["y"], r["w"], r["h"]
                if abs(px - x) <= 3 or abs(px - (x + w)) <= 3:
                    if y - 3 <= py <= y + h + 3:
                        on_edge = True; break
                if abs(py - y) <= 3 or abs(py - (y + h)) <= 3:
                    if x - 3 <= px <= x + w + 3:
                        on_edge = True; break
            if not on_edge and hits < 4:
                hits += 1
                report.warn(path, "连线端点", f"{label} 连线端点疑似悬空：({px:.0f},{py:.0f}) 不在任何节点边 3px 内")


def check_mask_over_line(svg: str, path: str, label: str, vw: float, vh: float, report: Report) -> None:
    rects = [r for r in collect_shapes(svg, vw, vh) if 12 <= r["w"] <= 320 and r["h"] <= 18]
    if not rects:
        return
    segments = []
    for m in PATH_RE.finditer(svg):
        segments.extend(straight_segments(parse_attrs(m.group(1)).get("d", "")))
    for m in LINE_RE.finditer(svg):
        a = parse_attrs(m.group(1))
        try:
            segments.append((float(a.get("x1", 0)), float(a.get("y1", 0)), float(a.get("x2", 0)), float(a.get("y2", 0))))
        except ValueError:
            continue
    hits = 0
    for r in rects:
        for x1, y1, x2, y2 in segments:
            if abs(y2 - y1) <= 1 and r["x"] - 2 <= min(x1, x2) <= r["x"] + r["w"] + 2 and min(y1, y2) - 2 <= r["y"] + r["h"] and max(y1, y2) + 2 >= r["y"]:
                if r["y"] + 2 < y1 < r["y"] + r["h"] - 2 or r["y"] + 2 < y2 < r["y"] + r["h"] - 2:
                    hits += 1
                    report.warn(path, "标签遮罩", f"{label} 疑似标签遮罩压住连线（遮罩 y={r['y']:.0f}~{r['y']+r['h']:.0f}）")
                    break
            if abs(x2 - x1) <= 1 and r["y"] - 2 <= min(y1, y2) <= r["y"] + r["h"] + 2 and min(x1, x2) - 2 <= r["x"] + r["w"] and max(x1, x2) + 2 >= r["x"]:
                hits += 1
                report.warn(path, "标签遮罩", f"{label} 疑似标签遮罩压住竖线（遮罩 x={r['x']:.0f}~{r['x']+r['w']:.0f}）")
                break
        if hits >= 4:
            break


def collect_class_rules(svg: str) -> dict[str, str]:
    rules = {}
    for style in STYLE_BLOCK_RE.findall(svg):
        for m in re.finditer(r"\.([A-Za-z_][A-Za-z0-9_-]*)\s*\{([^}]*)\}", style):
            decl = re.sub(r"\s+", " ", m.group(2)).strip().lower()
            rules.setdefault(m.group(1), set()).add(decl)  # type: ignore[arg-type]
    return rules


def text_width(text: str, font_size: float) -> float:
    """按字符类型估算文本宽度（px）。CJK 按 1.0em，西文按 0.56em，空格 0.3em。"""
    width = 0.0
    for ch in text:
        if CJK_RE.match(ch):
            width += font_size
        elif ch == " ":
            width += font_size * 0.3
        elif ch in "il.,:;'|!":
            width += font_size * 0.32
        elif ch in "mwMW@#%&":
            width += font_size * 0.85
        else:
            width += font_size * 0.56
    return width


def check_svg_structure(svg: str, path: str, label: str, report: Report) -> tuple[set[str], set[str], float, float]:
    ids = set(ID_ATTR_RE.findall(svg))
    classes = set(CLASS_SELECTOR_RE.findall(svg))

    if not re.search(r'\brole="img"', svg, re.I):
        report.warn(path, "可访问性", f"{label} 缺少 role=\"img\"")
    m = re.search(r'aria-labelledby="([^"]+)"', svg)
    if not m:
        report.warn(path, "可访问性", f"{label} 缺少 aria-labelledby")
    else:
        for ref in m.group(1).split():
            if ref not in ids:
                report.error(path, "可访问性", f"{label} 的 aria-labelledby 指向不存在的 id：{ref}")

    title = re.search(r"<title\b[^>]*>(.*?)</title>", svg, re.S | re.I)
    desc = re.search(r"<desc\b[^>]*>(.*?)</desc>", svg, re.S | re.I)
    if not title or not title.group(1).strip():
        report.warn(path, "可访问性", f"{label} 缺少非空 <title>")
    if not desc or not desc.group(1).strip():
        report.warn(path, "可访问性", f"{label} 缺少非空 <desc>")

    if not re.search(r'viewBox="[^"]+"', svg):
        report.warn(path, "结构", f"{label} 缺少 viewBox")

    dup = len(ID_ATTR_RE.findall(svg)) - len(ids)
    if dup:
        report.error(path, "结构", f"{label} 内部有 {dup} 个重复 id")

    # 引用完整性
    for ref in set(URL_REF_RE.findall(svg)) | set(HREF_ANCHOR_RE.findall(svg)):
        if ref not in ids:
            report.warn(path, "引用", f"{label} 引用了不存在的 id：#{ref}")

    vw = vh = 0.0
    vb = re.search(r'viewBox="([^"]+)"', svg)
    if vb:
        nums = vb.group(1).replace(",", " ").split()
        try:
            if len(nums) >= 4:
                vw, vh = float(nums[2]), float(nums[3])
            elif len(nums) == 2:
                vw, vh = float(nums[0]), float(nums[1])
        except ValueError:
            vw = vh = 0.0
    return ids, classes, vw, vh


def check_text_overflow(svg: str, path: str, label: str, report: Report) -> None:
    vb = re.search(r'viewBox="([^"]+)"', svg)
    if not vb:
        return
    nums = vb.group(1).replace(",", " ").split()
    try:
        if len(nums) >= 4:
            vw, vh = float(nums[2]), float(nums[3])
        elif len(nums) == 2:
            vw, vh = float(nums[0]), float(nums[1])
        else:
            return
    except ValueError:
        return
    if vw <= 0 or vh <= 0:
        return
    class_font_sizes = collect_class_font_sizes(svg)
    for m in TEXT_RE.finditer(svg):
        attrs = parse_attrs(m.group(1))
        content = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not content:
            continue
        try:
            x = float(attrs.get("x", "0"))
            y = float(attrs.get("y", "0"))
            inline_fs = attrs.get("font-size")
            if inline_fs:
                fs = float(re.sub(r"[^\d.]", "", inline_fs) or 12)
            else:
                fs = 12.0
                for cls in attrs.get("class", "").split():
                    if cls in class_font_sizes:
                        fs = class_font_sizes[cls]
                        break
        except ValueError:
            continue
        anchor = attrs.get("text-anchor", "start")
        width = text_width(content, fs)
        if anchor == "middle":
            left, right = x - width / 2, x + width / 2
        elif anchor == "end":
            left, right = x - width, x
        else:
            left, right = x, x + width
        if right > vw - 2 or left < 2:
            report.warn(
                path,
                "文字溢出",
                f"{label} 文本疑似越出画布：「{content[:24]}」（估算 {left:.0f}~{right:.0f}px，画布宽 {vw:.0f}）",
            )
        if y > vh - 2 or y < fs:
            report.warn(path, "文字溢出", f"{label} 文本疑似越出画布纵向：「{content[:24]}」y={y:.0f}，画布高 {vh:.0f}")


def straight_segments(d: str) -> list[tuple[float, float, float, float]]:
    """从 path 的 d 属性里抽出直线段（M/L/H/V），跳过曲线与弧线。"""
    tokens = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|-?\d+(?:\.\d+)?", d)
    segments: list[tuple[float, float, float, float]] = []
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    i = 0
    cmd = ""
    while i < len(tokens):
        tok = tokens[i]
        if re.fullmatch(r"[A-Za-z]", tok):
            cmd = tok
            i += 1
            if cmd in "Zz":
                cur = start
            continue
        if cmd in "Mm":
            x, y = float(tokens[i]), float(tokens[i + 1]); i += 2
            cur = (x, y); start = cur
            cmd = "L" if cmd == "M" else "l"
        elif cmd in "Ll":
            x, y = float(tokens[i]), float(tokens[i + 1]); i += 2
            if cmd == "l":
                x, y = cur[0] + x, cur[1] + y
            segments.append((cur[0], cur[1], x, y)); cur = (x, y)
        elif cmd in "Hh":
            x = float(tokens[i]); i += 1
            if cmd == "h":
                x = cur[0] + x
            segments.append((cur[0], cur[1], x, cur[1])); cur = (x, cur[1])
        elif cmd in "Vv":
            y = float(tokens[i]); i += 1
            if cmd == "v":
                y = cur[1] + y
            segments.append((cur[0], cur[1], cur[0], y)); cur = (cur[0], y)
        elif cmd in "Aa":
            i += 7
            if i < len(tokens) and not re.fullmatch(r"[A-Za-z]", tokens[i]):
                x, y = float(tokens[i]), float(tokens[i + 1]); i += 2
                cur = (x, y)
        elif cmd in "Cc":
            i += 6
        elif cmd in "SsQq":
            i += 4
        elif cmd in "Tt":
            i += 2
        else:
            i += 1
    return segments


def check_connectors(svg: str, path: str, label: str, report: Report) -> None:
    """启发式：单个直线段同时有较大的 dx、dy，视为疑似斜线连接。"""
    for m in PATH_RE.finditer(svg):
        d = parse_attrs(m.group(1)).get("d", "")
        for x1, y1, x2, y2 in straight_segments(d):
            if abs(x2 - x1) > 8 and abs(y2 - y1) > 8:
                report.warn(path, "连接器", f"{label} 存在疑似斜线连接（{x1:.0f},{y1:.0f} → {x2:.0f},{y2:.0f}）")
                return
    for m in LINE_RE.finditer(svg):
        a = parse_attrs(m.group(1))
        try:
            x1, y1 = float(a.get("x1", 0)), float(a.get("y1", 0))
            x2, y2 = float(a.get("x2", 0)), float(a.get("y2", 0))
        except ValueError:
            continue
        if abs(x2 - x1) > 8 and abs(y2 - y1) > 8:
            report.warn(path, "连接器", f"{label} 存在斜线 <line>（{x1:.0f},{y1:.0f} → {x2:.0f},{y2:.0f}）")
            return


def check_html(path: Path, text: str, report: Report) -> None:
    label_base = path.name
    if IFRAME_RE.search(text):
        report.warn(label_base, "页面整洁", "残留 iframe（应内联 SVG）")
    if re.search(r"overflow-x\s*:\s*(auto|scroll)", text, re.I):
        report.warn(label_base, "页面整洁", "存在横向滚动样式")
    if CJK_RE.search(text) and not re.search(r"Noto Sans (?:SC|TC|HK)", text):
        report.warn(label_base, "字体", "含中文但未引入 Noto Sans SC/TC 字体")

    svgs = SVG_BLOCK_RE.findall(text)
    if not svgs:
        report.warn(label_base, "结构", "没有找到内联 SVG")
        return
    report.info(label_base, "结构", f"内联 SVG {len(svgs)} 个")

    all_ids: dict[str, int] = {}
    class_rules: dict[str, set[str]] = {}
    class_owner_svgs: dict[str, int] = {}
    for index, svg in enumerate(svgs, 1):
        label = f"图{index}"
        ids, _, vw, vh = check_svg_structure(svg, label_base, label, report)
        for i in ids:
            all_ids[i] = all_ids.get(i, 0) + 1
        for cls, decls in collect_class_rules(svg).items():
            class_rules.setdefault(cls, set()).update(decls)
            class_owner_svgs[cls] = class_owner_svgs.get(cls, 0) + 1
        check_text_overflow(svg, label_base, label, report)
        check_text_fit(svg, label_base, label, vw, vh, report)
        check_connectors(svg, label_base, label, report)
        check_connector_endpoints(svg, label_base, label, vw, vh, report)
        check_mask_over_line(svg, label_base, label, vw, vh, report)
        check_ddd_relations(svg, label_base, label, report)
        check_connector_overlap(svg, label_base, label, report)
        check_figure_semantics(svg, label_base, label, report)

    collisions = sorted(i for i, n in all_ids.items() if n > 1)
    if collisions:
        report.error(label_base, "id 冲突", "多张内联 SVG 共享 id（必须按图加前缀）：" + "、".join(collisions[:10]))
    shared = sorted(cls for cls, n in class_owner_svgs.items() if n >= 2)
    if shared:
        report.warn(label_base, "class 冲突", "同名 class 跨多张内联 SVG 定义（建议按图加前缀）：" + "、".join(shared[:10]))
    cross = sorted(cls for cls, decls in class_rules.items() if len(decls) > 1)
    if cross:
        report.error(label_base, "class 冲突", "多张内联 SVG 的同名 class 定义不一致（样式会互相覆盖）：" + "、".join(cross[:10]))
    if class_rules:
        report.info(label_base, "class 前缀", f"共定义 {len(class_rules)} 个 class；内联多图必须统一加前缀")


def check_ddd_relations(svg: str, path: str, label: str, report: Report) -> None:
    head = (re.search(r"<title[^>]*>(.*?)</title>", svg, re.S) or [None, ""])[1] if False else ""
    mt = re.search(r"<title[^>]*>(.*?)</title>", svg, re.S)
    md = re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.S)
    text = (mt.group(1) if mt else "") + (md.group(1) if md else "")
    if "领域模型" not in text:
        return
    for name, key in (("仓储管理聚合", "管理"), ("工厂创建聚合", "创建"), ("领域服务依赖聚合", "依赖"), ("聚合发布事件", "发布")):
        if key not in svg:
            report.warn(path, "DDD 关系", f"{label} 缺少「{name}」关系标注；不能只把元素堆在图里")


def check_connector_overlap(svg: str, path: str, label: str, report: Report) -> None:
    segs = []
    for m in PATH_RE.finditer(svg):
        for x1, y1, x2, y2 in straight_segments(parse_attrs(m.group(1)).get("d", "")):
            segs.append((x1, y1, x2, y2))
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            x1, y1, x2, y2 = segs[i]
            a1, b1, a2, b2 = segs[j]
            if abs(y1 - y2) <= 1 and abs(b1 - b2) <= 1 and abs(y1 - b1) <= 1:
                lo1, hi1 = sorted((x1, x2)); lo2, hi2 = sorted((a1, a2))
                if min(hi1, hi2) - max(lo1, lo2) > 12:
                    report.warn(path, "连线重叠", f"{label} 存在水平线重叠（y={y1:.0f}），应错开或合并")
                    return
            if abs(x1 - x2) <= 1 and abs(a1 - a2) <= 1 and abs(x1 - a1) <= 1:
                lo1, hi1 = sorted((y1, y2)); lo2, hi2 = sorted((b1, b2))
                if min(hi1, hi2) - max(lo1, lo2) > 12:
                    report.warn(path, "连线重叠", f"{label} 存在竖线重叠（x={x1:.0f}），应错开或合并")
                    return


def check_figure_semantics(svg: str, path: str, label: str, report: Report) -> None:
    head = (re.search(r"<title[^>]*>(.*?)</title>", svg, re.S).group(1) if re.search(r"<title[^>]*>(.*?)</title>", svg, re.S) else "") + \
           (re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.S).group(1) if re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.S) else "")
    if "部署" in head and "infra 适配器" in svg:
        report.warn(path, "图语义", f"{label}：infra 适配器是进程内代码层，不应画成独立部署节点")
    if "时序" in head and "事务" not in svg:
        report.warn(path, "图语义", f"{label}：时序图缺事务边界说明（同步事务 vs 异步通知）")


def check_svg_file(path: Path, report: Report) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    ids, _, vw, vh = check_svg_structure(text, path.name, path.name, report)
    check_text_overflow(text, path.name, path.name, report)
    check_text_fit(text, path.name, path.name, vw, vh, report)
    check_connectors(text, path.name, path.name, report)
    check_connector_endpoints(text, path.name, path.name, vw, vh, report)
    check_mask_over_line(text, path.name, path.name, vw, vh, report)
    check_ddd_relations(text, path.name, path.name, report)
    check_connector_overlap(text, path.name, path.name, report)
    check_figure_semantics(text, path.name, path.name, report)
    if not ids:
        report.info(path.name, "结构", "SVG 没有 id（若后续要内联多图，建议预留）")


def iter_targets(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for raw in paths:
        p = Path(raw).resolve()
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out.extend(sorted(p.rglob("*.html")))
            out.extend(sorted(p.rglob("*.svg")))
    return [p for p in out if p.suffix.lower() in {".html", ".svg"}]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="架构配图自检")
    parser.add_argument("paths", nargs="+", help="HTML/SVG 文件或目录")
    parser.add_argument("--strict", action="store_true", help="warning 也按失败处理")
    args = parser.parse_args(argv)

    targets = iter_targets(args.paths)
    if not targets:
        print("没有找到 .html/.svg 文件", file=sys.stderr)
        return 2

    report = Report(strict=args.strict)
    for path in targets:
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix.lower() == ".html":
            check_html(path, text, report)
        else:
            check_svg_file(path, report)
    return report.print()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
