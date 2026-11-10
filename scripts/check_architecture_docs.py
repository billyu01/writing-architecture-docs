#!/usr/bin/env python3
"""架构设计文档自检（只依赖 Python 标准库）。

用法：
  python3 check_architecture_docs.py <文档或目录> [--prd PRD.md] [--html 架构.html] [--strict]

它只做「机器可查」的检查，不做业务判断。检查项：
  1. 相对链接 / 图片引用是否存在（含跨目录、带锚点的链接）
  2. TODO / TBD / 待补 等占位符残留
  3. 架构总览的必备章节是否齐全（事实基线 / 业务分析 / 领域建模 / 逻辑架构 / 流程 /
     部署 / 决策 / 功能与非功能 / 组件清单 / 选型 / 安全 / 扩展 / 图索引 / 修订史 / 权威顺序）
  4. 决策表是否带「备选」「代价/推翻条件」列
  5. 模块分册的必备章节是否齐全（职责边界 / 能力 / 流程 / 接口 / 交互协议 / 数据 / 错误 / 验收 / 状态）
  6. 组件清单里的分册链接是否都能打开；分册数量与清单行数是否一致
  7. 图索引与实际图资产是否互相对得上（正文引用了图但索引没登记 / 资产目录有图但正文没引用）
  8. 与 PRD 的编号追溯（--prd）：文档引用的 FR/NFR/GATE/OPEN 编号是否在 PRD 中存在
  9. HTML 版（--html）：是否残留 iframe、内联 SVG 是否被索引

退出码：0 = 没有 error；1 = 有 error。warning 不改变退出码，除非 --strict。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"

PLACEHOLDER_RE = re.compile(r"(TODO|TBD|FIXME|XXX|待补充|待补|待定|占位符|placeholder)", re.I)
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
ID_RE = re.compile(r"\b(FR|NFR|GATE|OPEN|C)-[A-Z0-9][A-Z0-9-]*\b")

OVERVIEW_SECTIONS = {
    "引言与目标": [r"引言", r"目的与范围", r"目标"],
    "架构约束": [r"架构约束", r"约束", r"现状"],
    "业务背景": [r"业务背景", r"业务分析", r"业务目标"],
    "领域建模": [r"领域建模", r"领域模型"],
    "逻辑视图": [r"逻辑视图", r"逻辑架构"],
    "进程视图": [r"进程视图", r"运行时视图"],
    "开发视图": [r"开发视图", r"代码组织"],
    "物理视图": [r"物理视图", r"物理架构", r"部署"],
    "场景视图": [r"场景视图", r"用例视图", r"贯穿用例"],
    "核心业务流程": [r"核心业务流程", r"核心流程", r"业务流程"],
    "组件清单": [r"组件规划", r"组件清单", r"构建块"],
    "架构决策": [r"架构决策", r"技术决策", r"决策"],
    "功能与非功能": [r"功能与非功能", r"非功能", r"功能需求"],
    "技术选型": [r"技术选型", r"选型"],
    "横切概念": [r"横切", r"安全与信任", r"可观测"],
    "扩展性": [r"扩展性", r"扩展与迭代", r"演进"],
    "图资产索引": [r"图资产索引", r"图索引", r"图表索引"],
    "修订史": [r"修订史", r"变更记录", r"修订记录"],
    "附录": [r"附录"],
}

MODULE_SECTIONS = {
    "职责边界": [r"定位", r"职责", r"边界"],
    "业务能力": [r"业务能力", r"能力"],
    "流程与时序": [r"流程", r"时序"],
    "接口设计": [r"接口"],
    "交互协议": [r"交互协议", r"协议"],
    "数据/状态设计": [r"数据", r"集合", r"状态设计", r"存储"],
    "错误分类": [r"错误"],
    "验收门禁": [r"验收", r"门禁"],
    "实现状态与差距": [r"实现状态", r"差距", r"状态"],
}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.M)


class Report:
    def __init__(self, strict: bool = False) -> None:
        self.rows: list[tuple[str, str, str, str]] = []  # level, file, check, message
        self.strict = strict

    def add(self, level: str, path: Path, check: str, message: str) -> None:
        self.rows.append((level, str(path), check, message))

    def error(self, path: Path, check: str, message: str) -> None:
        self.add(ERROR, path, check, message)

    def warn(self, path: Path, check: str, message: str) -> None:
        self.add(WARN, path, check, message)

    def info(self, path: Path, check: str, message: str) -> None:
        self.add(INFO, path, check, message)

    def print(self) -> int:
        order = {ERROR: 0, WARN: 1, INFO: 2}
        for level, path, check, message in sorted(self.rows, key=lambda r: (order[r[0]], r[1], r[2])):
            print(f"[{level}] {path} :: {check} :: {message}")
        counts = {level: sum(1 for r in self.rows if r[0] == level) for level in (ERROR, WARN, INFO)}
        print()
        print(f"汇总：{counts[ERROR]} 个 error，{counts[WARN]} 个 warning，{counts[INFO]} 条提示。")
        if counts[ERROR] > 0:
            return 1
        if self.strict and counts[WARN] > 0:
            return 1
        return 0


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def md_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files = []
    for p in sorted(root.rglob("*.md")):
        if any(part in {".git", ".tmp", "node_modules", "assets"} for part in p.parts):
            continue
        if p.name.lower() in {"readme.md", "changelog.md", "contributing.md"}:
            continue
        files.append(p)
    return files


def resolve_link(base: Path, target: str) -> Path | None:
    raw = target.strip()
    if raw.startswith(("http://", "https://", "mailto:", "tel:", "#", "data:")):
        return None
    raw = raw.split("#", 1)[0].strip()
    if not raw:
        return None
    raw = raw.replace("%20", " ")
    return (base.parent / raw).resolve()


def check_links(path: Path, text: str, report: Report) -> list[str]:
    refs: list[str] = []
    for m in LINK_RE.finditer(text):
        target = m.group(1)
        resolved = resolve_link(path, target)
        if resolved is None:
            continue
        refs.append(str(resolved))
        if not resolved.exists():
            report.error(path, "链接", f"引用不存在：{target}")
    return refs


def extract_headings(text: str) -> list[str]:
    return [m.group(2).strip() for m in HEADING_RE.finditer(text)]


def missing_sections(headings: list[str], expected: dict[str, list[str]]) -> list[str]:
    joined = "\n".join(headings)
    missing = []
    for name, patterns in expected.items():
        if not any(re.search(p, joined) for p in patterns):
            missing.append(name)
    return missing


def split_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^#{2,3}\s+(.+)$", text, re.M))
    out = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1).strip(), text[start:end]))
    return out


def check_four_plus_one(path: Path, text: str, report: Report) -> None:
    joined = "\n".join(h for h, _ in split_sections(text))
    required = {
        "逻辑视图": r"逻辑视图|逻辑架构",
        "进程视图": r"进程视图|进程模型|运行时视图",
        "开发视图": r"开发视图|代码组织|开发与构建",
        "物理视图": r"物理视图|物理部署|部署架构",
        "场景视图": r"场景视图|用例视图|贯穿用例",
    }
    for name, pat in required.items():
        if not re.search(pat, joined):
            level = "error" if name in {"进程视图", "开发视图", "场景视图"} else "warn"
            getattr(report, level)(path, "4+1 视图", f"缺少视图：{name}")


def check_domain_model_elements(path: Path, text: str, report: Report) -> None:
    domain = [body for title, body in split_h2(text) if "领域" in title]
    if not domain:
        return
    blob = "\n".join(domain)
    required = {
        "限界上下文": r"限界上下文|上下文边界",
        "上下文映射/集成": r"上下文映射|防腐层|客户-供应商|发布语言|集成",
        "聚合/聚合根": r"聚合",
        "实体与值对象": r"值对象",
        "领域事件": r"领域事件",
        "领域服务": r"领域服务",
        "仓储": r"仓储",
        "工厂": r"工厂",
        "生命周期/状态": r"生命周期|状态机|状态迁移",
        "不变量": r"不变量",
    }
    for name, pat in required.items():
        if not re.search(pat, blob):
            report.warn(path, "领域建模", f"领域建模缺少要素：{name}（ER 图不能替代领域建模）")


def check_code_discipline(path: Path, text: str, report: Report) -> None:
    codes = set(re.findall(r"\b(?:FR|NFR|GATE|OPEN|D|U|A)[-]?[0-9][A-Za-z0-9-]*\b", text))
    if not codes:
        return
    headings = extract_headings(text)
    bare_in_heading = [h for h in headings if re.search(r"\b(?:FR|NFR|GATE|OPEN)[-]?[0-9]", h)]
    if bare_in_heading:
        report.warn(path, "代号纪律", "标题里出现裸代号：" + "、".join(bare_in_heading[:5]))
    has_index = any(re.search(r"编号索引|代号说明|术语与编号|缩写", h) for h in headings)
    if not has_index:
        report.warn(path, "代号纪律", f"正文出现 {len(codes)} 个代号，但没有「编号/代号说明」章节；正文应优先用中文名称")
    # 同一行只有代号没有中文解释：启发式
    bare_only = []
    for line in text.splitlines():
        if re.search(r"\b(?:FR|NFR|GATE)[-]?[0-9]", line) and not re.search(r"[\u4e00-\u9fff]", line):
            bare_only.append(line.strip()[:60])
    if bare_only:
        report.warn(path, "代号纪律", "存在只有代号没有中文说明的行：" + "；".join(bare_only[:3]))


def check_build_commands(path: Path, text: str, report: Report) -> None:
    for i, line in enumerate(text.splitlines(), 1):
        if re.search(r"build_template\.py|embed_svg\.py|shasum|重建命令|rebuild", line, re.I):
            report.warn(path, "写作边界", f"第 {i} 行出现构建/重建动作，应移到 README 或运维文档，不写进架构正文")


def split_h2(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^##\s+(.+)$", text, re.M))
    out = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1).strip(), text[start:end]))
    return out


def check_section_depth(path: Path, text: str, report: Report) -> None:
    targets = ("功能", "选型", "横切", "扩展")
    for title, body in split_h2(text):
        if not any(k in title for k in targets):
            continue
        content = [ln for ln in body.splitlines() if ln.strip() and not re.fullmatch(r"[|\-\s:]+", ln.strip())]
        if len(content) < 6:
            report.warn(path, "章节深度", f"「{title}」内容过少（{len(content)} 行），至少要有结论表/关键约束/失败处理/量化指标")


def check_flow_and_view_figures(path: Path, text: str, report: Report) -> None:
    index_lines = [ln for ln in text.splitlines() if re.match(r"^\|\s*\d+[-–]\d+\s*\|", ln.strip())]
    seq_count = sum(1 for ln in index_lines if "时序" in ln)
    if seq_count < 2:
        report.warn(path, "核心流程", f"图索引里只有 {seq_count} 张时序图；核心业务流程至少两条，应各配一张时序图")
    for name, pat in (("限界上下文/集成", r"上下文"), ("DDD 领域模型", r"领域模型"), ("逻辑视图", r"逻辑"),
                      ("进程视图", r"进程"), ("开发视图", r"开发"), ("物理部署", r"部署|物理"),
                      ("状态机", r"状态机|生命周期"), ("Outbox 事件流", r"outbox|事件流"), ("账本/对账", r"对账|账本")):
        if not any(re.search(pat, ln) for ln in index_lines):
            report.warn(path, "图种覆盖", f"图索引里没有{name}的图")


def check_correctness(path: Path, text: str, report: Report) -> None:
    for i, line in enumerate(text.splitlines(), 1):
        if "outbox" in line and ("事务外" in line or "事务之外" in line):
            report.warn(path, "一致性", f"第 {i} 行：outbox 不应写在事务外，应使用事务内 outbox")
    if "幂等键" in text and ("TTL" not in text and "清理" not in text and "过期" not in text):
        report.warn(path, "一致性", "出现幂等键但没有 TTL/清理规范")
    if re.search(r"就绪|readyz", text) and re.search(r"S3 桶可达|短信适配器初始化", text):
        report.warn(path, "一致性", "就绪探针不宜把外部依赖（S3/短信）当硬门，应降级为告警+运行时降级")
    if re.search(r"两个聚合|跨聚合", text) and re.search(r"同事务|同一事务|一个事务", text):
        report.warn(path, "一致性", "出现「两个聚合/跨聚合」与「同事务」并存的表述，属于聚合一致性边界矛盾")


def check_external_review_items(path: Path, text: str, report: Report) -> None:
    # 积分账户维度歧义
    if "points_balance" in text and re.search(r"(?<![a-z_])member_id 唯一", text) and "store_id" in text:
        report.warn(path, "评审项", "积分余额按 member_id 唯一但流水含 store_id，需明确账户归属（会员级/门店级）")
    # 手机号加密
    if "phone_hash" in text and "phone_encrypted" not in text:
        report.warn(path, "评审项", "手机号只有 hash，无法发送短信；需 hash + 加密 + 脱敏三字段")
    # 幂等 TTL/保留冲突
    if "幂等键保留 30 天" in text and "TTL 24" in text:
        report.warn(path, "评审项", "请求幂等 TTL 与幂等记录保留期不一致，需区分请求幂等与业务唯一约束")
    # outbox 消费机制
    if "outbox" in text and "locked_by" not in text:
        report.warn(path, "评审项", "outbox 缺消费状态机/原子领取/租约字段（locked_by、locked_until）")
    # 充值账户
    if "充值" in text and "store_accounts" not in text and "门店额度账户" not in text:
        report.warn(path, "评审项", "充值对象未定义（门店额度/会员储值/预付资金），缺账户主体")
    # RBAC
    if "安全" in text and "角色" not in text and "RBAC" not in text:
        report.warn(path, "评审项", "安全章节缺角色权限矩阵")
    # 索引清单
    if "数据模型" in text and "索引清单" not in text and "索引" not in text:
        report.warn(path, "评审项", "数据模型缺索引清单")
    # 容量模型
    if "非功能" in text and "容量模型" not in text:
        report.warn(path, "评审项", "非功能章节缺容量模型（门店/会员/流水/峰值 QPS）")
    # 模板 V2：文档信息/摘要/设计卡/追溯/接口/测试
    for name, key in (("文档信息", "文档信息"), ("架构摘要", "架构摘要"), ("关键机制设计卡", "设计卡"),
                      ("需求追溯", "需求→设计"), ("核心接口清单", "核心接口"), ("测试与验收", "测试与验收")):
        if key not in text:
            report.warn(path, "模板项", f"缺少「{name}」；建议按模板 V2 补齐")
    if "只有应用 Deployment" in text and "worker Deployment" in text:
        report.warn(path, "部署一致性", "部署约束写「只有应用 Deployment」但与 web/worker 两类 Deployment 不一致")


def check_logical_contract(path: Path, text: str, report: Report) -> None:
    logical = [body for title, body in split_sections(text) if "逻辑视图" in title or "逻辑架构" in title]
    if not logical:
        return
    blob = "\n".join(logical)
    for label, pat in (("职责", r"职责|负责"), ("对外接口", r"接口"), ("依赖方向", r"依赖")):
        if not re.search(pat, blob):
            report.warn(path, "逻辑视图", f"逻辑视图缺少「{label}」列或说明；每个模块应写清六项")


def check_overview(path: Path, text: str, report: Report) -> None:
    check_four_plus_one(path, text, report)
    check_domain_model_elements(path, text, report)
    check_code_discipline(path, text, report)
    check_build_commands(path, text, report)
    check_section_depth(path, text, report)
    check_logical_contract(path, text, report)
    check_flow_and_view_figures(path, text, report)
    check_correctness(path, text, report)
    check_external_review_items(path, text, report)
    headings = extract_headings(text)
    for name in missing_sections(headings, OVERVIEW_SECTIONS):
        level = ERROR if name in {"事实基线", "逻辑架构", "核心流程", "物理部署", "核心技术决策"} else WARN
        getattr(report, level.lower())(path, "总览章节", f"缺少章节：{name}")

    # 决策表：表头必须显式给「备选」「代价/推翻条件」
    decision_heading = next((h for h in headings if re.search(r"决策", h)), None)
    if decision_heading:
        start = text.find(decision_heading)
        segment = text[start : start + 3000]
        if "备选" not in segment:
            report.warn(path, "决策表", "决策章节未见「备选」列，决策会退化成结论罗列")
        if not re.search(r"代价|推翻|取舍", segment):
            report.warn(path, "决策表", "决策章节未见「代价/推翻条件」，无法判断决策可逆性")

    # 图索引 vs 正文引用
    assets_root = path.parent / "assets"
    img_targets = set()
    for m in IMG_RE.finditer(text):
        target = m.group(1).strip()
        if target.startswith(("http://", "https://", "data:")):
            continue
        clean = target.split("#", 1)[0]
        img_targets.add(clean)
    # 图注里通常会链接交互源 .html / .svg，也算「被正文引用」
    for m in LINK_RE.finditer(text):
        target = m.group(1).strip()
        if target.startswith(("http://", "https://", "data:", "#", "mailto:")):
            continue
        clean = target.split("#", 1)[0]
        if clean.lower().endswith((".html", ".svg", ".png")):
            img_targets.add(clean)
    indexed = re.search(r"(图资产索引|图索引|图表索引)", text) is not None
    if img_targets and not indexed:
        report.warn(path, "图索引", "正文引用了图，但没有「图资产索引」章节")
    if assets_root.is_dir():
        asset_files = {str(p.name) for p in assets_root.iterdir() if p.suffix.lower() in {".svg", ".html", ".png"}}
        referenced_names = {Path(t).name for t in img_targets}
        orphan = sorted(asset_files - referenced_names)
        if orphan:
            report.warn(path, "图索引", "资产目录里有图未被正文引用：" + "、".join(orphan[:8]))


def check_module(path: Path, text: str, report: Report) -> None:
    headings = extract_headings(text)
    for name in missing_sections(headings, MODULE_SECTIONS):
        report.warn(path, "模块分册章节", f"缺少章节：{name}")


def check_component_list(path: Path, text: str, report: Report) -> None:
    module_links = re.findall(r"\]\(([^)]*modules/[^)#]+)", text)
    if not module_links:
        return
    resolved = [resolve_link(path, t) for t in module_links]
    resolved = [p for p in resolved if p is not None]
    existing = [p for p in resolved if p.exists()]
    report.info(path, "组件清单", f"清单链接 {len(resolved)} 条，可打开 {len(existing)} 条")
    if len(existing) != len(resolved):
        report.error(path, "组件清单", "存在打不开的分册链接")


def check_placeholders(path: Path, text: str, report: Report) -> None:
    for m in PLACEHOLDER_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        report.warn(path, "占位符", f"第 {line} 行残留：{m.group(0)}")


def check_prd_ids(path: Path, text: str, prd: Path, report: Report) -> None:
    if not prd.exists():
        report.error(path, "PRD 追溯", f"PRD 不存在：{prd}")
        return
    prd_text = read_text(prd)
    prd_ids = set(m.group(0) for m in ID_RE.finditer(prd_text))
    doc_ids = set(m.group(0) for m in ID_RE.finditer(text))
    missing = sorted(doc_ids - prd_ids)
    if missing:
        report.warn(path, "PRD 追溯", "以下编号在 PRD 中找不到：" + "、".join(missing[:15]))
    report.info(path, "PRD 追溯", f"文档引用编号 {len(doc_ids)} 个，PRD 中缺失 {len(missing)} 个")


ANCHOR_RE = re.compile(r"([A-Za-z0-9_./-]+\.(?:py|md|yml|yaml|json|ts|tsx|js|html|svg|toml|cfg|ini)):(\d+)(?:-(\d+))?")


def resolve_anchor_path(raw: str, doc: Path, repo_root: Path) -> Path | None:
    """按 仓库根 → 文档目录 → services/*/ 三种基准解析锚点路径。"""
    candidates = [(repo_root / raw), (doc.parent / raw)]
    for base in candidates:
        if base.exists() and base.is_file():
            return base.resolve()
    if "/" in raw and not raw.startswith("services/"):
        for hit in repo_root.glob("services/*/" + raw):
            if hit.is_file():
                return hit.resolve()
    return None


def check_anchors(path: Path, text: str, repo_root: Path, report: Report) -> None:
    """核验「文件:行号」锚点：能定位的查行号越界；定位不了的只汇总，不逐条报警。"""
    checked = 0
    unresolved: list[str] = []
    out_of_range: list[str] = []
    seen: set[tuple[str, int]] = set()
    for m in ANCHOR_RE.finditer(text):
        raw, line = m.group(1), int(m.group(2))
        if raw.startswith(("http://", "https://", "/")):
            continue
        target = resolve_anchor_path(raw, path, repo_root)
        if target is None:
            unresolved.append(f"{raw}:{line}")
            continue
        key = (str(target), line)
        if key in seen:
            continue
        seen.add(key)
        checked += 1
        try:
            total = sum(1 for _ in target.open(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if line < 1 or line > total:
            out_of_range.append(f"{raw}:{line}（文件 {total} 行）")
    if out_of_range:
        report.warn(path, "行号锚点", "锚点越界：" + "；".join(out_of_range[:10]) + (f"；共 {len(out_of_range)} 处" if len(out_of_range) > 10 else ""))
    if unresolved:
        sample = "、".join(unresolved[:8])
        report.info(path, "行号锚点", f"{len(unresolved)} 个锚点无法定位（多为相对服务目录的简写，需人工确认）：{sample}")
    if checked:
        report.info(path, "行号锚点", f"核验 {checked} 个可定位锚点，越界 {len(out_of_range)} 个")


def check_html(html: Path, report: Report) -> None:
    if not html.exists():
        report.error(html, "HTML 版", "文件不存在")
        return
    text = read_text(html)
    iframes = len(re.findall(r"<iframe\b", text, re.I))
    if iframes:
        report.warn(html, "HTML 版", f"残留 {iframes} 个 iframe（应内联 SVG，避免滚动/裁切）")
    inline_svgs = len(re.findall(r"<svg\b", text, re.I))
    report.info(html, "HTML 版", f"内联 SVG {inline_svgs} 个")
    if re.search(r"overflow-x\s*:\s*(auto|scroll)", text, re.I):
        report.warn(html, "HTML 版", "页面存在横向滚动样式（overflow-x: auto/scroll）")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="架构设计文档自检")
    parser.add_argument("root", help="架构文档或文档目录")
    parser.add_argument("--prd", help="PRD 路径，用于编号追溯")
    parser.add_argument("--html", help="HTML 可视版路径")
    parser.add_argument("--repo-root", default=".", help="仓库根目录，用于核验「文件:行号」锚点")
    parser.add_argument("--strict", action="store_true", help="warning 也按失败处理")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"路径不存在：{root}", file=sys.stderr)
        return 2

    report = Report(strict=args.strict)
    files = md_files(root)
    if not files:
        print("没有找到 markdown 文档", file=sys.stderr)
        return 2

    prd = Path(args.prd).resolve() if args.prd else None
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()
    for path in files:
        text = read_text(path)
        check_placeholders(path, text, report)
        check_links(path, text, report)
        check_anchors(path, text, repo_root, report)
        if re.search(r"modules/", text) and path.parent.name != "modules":
            check_component_list(path, text, report)
        if "modules" in path.parts:
            check_module(path, text, report)
        elif "架构" in path.name or "architecture" in path.name.lower():
            check_overview(path, text, report)
        if prd is not None:
            check_prd_ids(path, text, prd, report)

    if args.html:
        check_html(Path(args.html).resolve(), report)

    return report.print()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
