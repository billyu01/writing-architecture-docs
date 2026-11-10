# 09 · 理论依据索引（完整方法论在 theories/）

> 各理论文件只引用来源文档中的示例（arc42、C4、SRE、ADR 等），不自行编造业务案例；示例链接见各文件末尾。
>
> 本文件只做索引；每个方法论的完整内容（定义、核心概念、可操作步骤、产物、检查清单、误用、出处）在 `theories/` 对应文件。
> agent 读取顺序：`SKILL.md` → `08-methodology.md`（每步方法）→ 本索引 → `theories/` 下 01–08 文件（理论细节）。

## 1. 理论 → 文件

| 理论 | 详细文件 | 主要解决 |
|---|---|---|
| arc42 / 4+1 / C4 / IEEE 42010 / UML | `theories/01-views-and-documentation.md` | 文档怎么组织、视图怎么切、图怎么画 |
| DDD（战略+战术） | `theories/02-ddd.md` | 领域边界、聚合、事件、仓储/工厂/服务 |
| ISO 25010 / 质量场景 / ATAM / SRE / fitness function | `theories/03-quality-attributes.md` | 质量目标怎么定义、权衡、验收 |
| ACID / CAP / PACELC / 幂等 / Outbox / Saga | `theories/04-consistency-and-messaging.md` | 事务边界、一致性、异步投递、补偿 |
| Parnas / Clean / Hexagonal / 包原则 / Conway | `theories/05-modularity-and-dependencies.md` | 模块怎么切、依赖怎么指、代码怎么组织 |
| 可靠性 / 故障域 / RPO-RTO / 可观测 / K8s | `theories/06-reliability-and-deployment.md` | 高可用、部署拓扑、故障恢复 |
| STRIDE / 信任边界 / OWASP / EIP / API 契约 | `theories/07-security-and-integration.md` | 威胁建模、权限、集成模式、契约 |
| ADR / MADR / 决策质量 / ATAM 权衡 / 评审 | `theories/08-decisions-and-review.md` | 决策留痕、权衡、评审闭环 |

## 2. 每个文件的结构

每个理论文件（`theories/` 下 01–08）都包含完整方法论与示例：

1. **定义与适用**：这个理论是什么、什么场景用、什么场景不用。
2. **核心概念**：术语表/模型/分类，给出可操作定义。
3. **使用步骤**：编号步骤，能直接照做。
4. **产物**：表格/图/清单的模板或字段。
5. **检查清单**：可勾选的验收项。
6. **常见误用**：错误做法、后果、修正。
7. **与其他理论关系**：如何组合使用。
8. **出处**：原始来源，供溯源。

## 3. 怎么选读

- 写文档结构：读 01。
- 写领域建模：读 02。
- 写非功能/验收：读 03。
- 写事务/异步/幂等：读 04。
- 写逻辑/开发视图：读 05。
- 写物理部署/高可用：读 06。
- 写安全/接口/集成：读 07。
- 写决策/评审：读 08。

## 4. 外部链接原则

详细文件内保留原始出处链接，但**不要求联网**：agent 以文件内的方法、步骤、清单为准；链接只用于需要原文时溯源。
