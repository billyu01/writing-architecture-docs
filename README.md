# writing-architecture-docs

一套可复用的系统架构设计文档技能：从需求与约束出发，用 arc42 + 4+1 视图 + DDD 组织架构文档，并用可机检的质量门、配图规范和验证流程保证文档能指导研发、通过评审、长期维护。

## 适用场景

- 新写或重写系统架构设计文档（架构总览、模块详细设计、技术选型、架构决策记录）。
- 架构文档被反馈「不完整、前后不一致、图看不到、无法约束实现、评审被打回」。
- 把需求文档、旧架构或代码现状落成一份可约束开发的权威架构文档。
- 交付前做文档质量自检、配图验收与独立评审修复。

## 目录结构

```text
writing-architecture-docs/
├── SKILL.md                        # 技能入口：原则、骨架、硬规则、质量门、配图入口
├── references/
│   ├── 01-workflow.md              # 11 阶段工作流
│   ├── 02-document-set.md          # 文档体系、权威顺序、编号与锚点
│   ├── 03-quality-gates.md         # 六维质量、检查清单、修复回路
│   ├── 04-user-confirmation.md     # 必确认事项、问法、未决台账
│   ├── 05-standards.md             # arc42 + 4+1 + DDD 标准映射
│   ├── 06-correctness.md           # 一致性红线与常见 P0
│   ├── 07-validation.md            # 结构/内容/图三级验证
│   ├── 08-methodology.md           # 每一步的方法与理论依据
│   ├── 09-theories.md              # 理论索引
│   ├── diagrams/                   # 架构图规范（图种、流程、嵌入、验收、语义）
│   └── theories/                   # 理论细节（视图、DDD、质量、一致性、模块化、可靠性、安全集成、决策）
├── assets/                         # 架构总览、模块详设、跟踪模板、图清单示例
└── scripts/                        # 文档自检、配图自检、SVG 内联、截图检查
```

## 安装

把整个 `writing-architecture-docs` 目录复制到你的技能目录，例如：

```bash
mkdir -p ~/.agents/skills
cp -R writing-architecture-docs ~/.agents/skills/
```

不同运行环境的技能目录可能不同；以实际加载路径为准。

## 使用

1. 先读 `SKILL.md`，按 11 阶段推进。
2. 需要细则时按阶段读 `references/01`–`09`。
3. 画架构图时读 `references/diagrams/`；通用画法细节参考外部 `diagram-design` 技能。
4. 写文档直接复制 `assets/` 里的模板。
5. 定稿前跑检查脚本，重建 HTML，并按 `references/07-validation.md` 做三级验证。

## 检查命令

```bash
python3 scripts/check_architecture_docs.py <文档目录> --html <可视版.html>
python3 scripts/check_architecture_diagrams.py <文档.html 或 assets>
python3 scripts/embed_svg.py --manifest figures.json
python3 scripts/render_check.py <文档.html> --widths 1400 --height 1000
```

合格标准：文档检查与配图检查均为 0 error；warning 逐条判断；配图官方自检全过；连续两次构建字节一致；正例通过、反例被拦下。

## 说明

- 通用画图能力不在本包内，仍使用外部 `diagram-design` 技能；本包负责「架构文档要哪些图、怎么验收、怎么嵌入」。
- 本包为通用方法论，不绑定具体项目；示例引用公开来源（arc42、C4、SRE、ADR 等）。
