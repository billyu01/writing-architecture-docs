# 08 · 架构设计方法论：每一步的方法与理论依据

> 本文回答：架构设计从接单到评审，每一步「怎么做、为什么这么做、依据哪个理论」。
> 标准结构映射见 `05-standards.md`；**理论细节（内化、可直接读）见 `09-theories.md`**；质量检查见 `03-quality-gates.md`；正确性红线见 `06-correctness.md`。

## 0. 三条总原则

1. **视图驱动（View-driven）**：不同利益相关者关心不同视图，不能一份文字包打天下（IEEE 42010；Kruchten 4+1）。
2. **权衡驱动（Trade-off-driven）**：每个关键决策都有备选、代价、推翻条件（ATAM；ADR）。
3. **可验证（Verifiable）**：每个结论能对应到证据、场景、测试或监控（质量属性场景；fitness function）。

## 1. 全链路：步骤 / 方法 / 理论依据 / 产物 / 判据

| # | 步骤 | 要回答的问题 | 方法 | 理论依据 | 产物 | 完成判据 |
|---|---|---|---|---|---|---|
| 1 | 接单与范围 | 做什么、不做什么、给谁看 | 原话清单、交付物清单、范围外清单、读者分层 | IEEE 42010（stakeholders/concerns/viewpoints）；arc42 §1（引言与目标） | 范围与读者表 | 用户能确认「做什么/交什么」；范围外显式 |
| 2 | 约束与现状 | 哪些前提不能动 | 事实基线、技术/组织/法规约束，每条带依据 | arc42 §2（Constraints）；TOGAF 约束思想 | 约束表（事实/依据/影响） | 每条约束有依据；冲突约束已上报 |
| 3 | 业务背景与质量目标 | 业务怎么运转、成功标准是什么 | 价值链、角色边界、质量属性场景（刺激-响应-度量） | arc42 §1/§3；ISO/IEC 25010 质量模型；ATAM 质量属性场景 | 业务分析、成功标准、质量目标 | 每个质量目标可度量；每个角色有「不做什么」 |
| 4 | 系统上下文 | 系统边界外有谁、走什么协议 | 上下文图、外部系统清单、协议/数据流 | C4 System Context；arc42 §3（Context & Scope）；DDD Context Map（外部部分） | 系统上下文图 + 上下文表 | 外部系统/角色/协议齐全；边界清晰 |
| 5 | 领域建模 | 领域里有哪些概念、边界与一致性在哪 | 统一语言、限界上下文、上下文映射、聚合/实体/值对象、领域事件、仓储/工厂/服务 | DDD（Evans 2003；Vernon 2013）；UML Class Diagram；Context Mapping（ACL/OHS/PL/Shared Kernel） | 领域模型图、聚合表、事件表、不变量 | 每个聚合有边界与不变量；上下文关系有方向与模式 |
| 6 | 逻辑架构 | 系统怎么切、模块职责与依赖 | 按业务能力/上下文切分；每模块六项；依赖规则/矩阵；结构风格选择（分层/六边形/模块化单体） | Kruchten 4+1 Logical View；arc42 §5 Building Block View；C4 Component；Parnas 信息隐藏与模块化；Clean/Hexagonal Architecture | 逻辑视图图、模块表、接口目录、依赖矩阵 | 每模块职责/接口/依赖/不做齐全；无环、无跨层直连 |
| 7 | 进程/运行时 | 怎么跑、并发/事务/失败怎么处理 | 进程/协程模型、同步/异步边界、事务与锁、租约、重试、降级、容量 | Kruchten 4+1 Process View；arc42 §6 Runtime View；UML Sequence/State；ACID；CAP/PACELC；Transactional Outbox / Saga（Richardson） | 进程视图、事务边界、失败与恢复方案 | 每条关键路径有事务/失败/重试说明；无「事务外 outbox」 |
| 8 | 开发视图 | 代码怎么组织、怎么构建测试 | 分层/包结构、依赖规则、构建制品、测试分层、本地开发 | Kruchten 4+1 Development View；arc42 §5/§8；C4 Code；Clean Architecture 依赖规则；包设计原则（REP/CCP/CRP、ADP/SDP/SAP）；Conway 定律 | 开发视图图、目录结构、构建/测试策略 | 依赖方向可机检；测试分层覆盖单元/集成/契约 |
| 9 | 物理/部署架构 | 装在哪、几个副本、网络与存储怎么放 | 逻辑块→部署单元映射；真实分区/信任边界；协议端口；存储拓扑；副本/故障域/扩缩容；探针/观测 | Kruchten 4+1 Physical View；arc42 §7 Deployment View；C4 Deployment；UML Deployment Diagram；可靠性（副本/故障域）；Kubernetes 模式 | 部署图、部署单元表、网络/边界表、容量/SLO | 每节点有角色/副本/版本；每路径有协议/端口；进程内层不当节点 |
| 10 | 数据架构 | 真源在哪、怎么一致、怎么归档 | 数据模型/索引、事务边界、缓存策略、读写模型、生命周期/归档、备份恢复 | ER 模型；DDD Repository；CQRS/Event Sourcing（Fowler）；CAP；数据生命周期管理 | 数据模型、索引清单、生命周期策略 | 索引与查询匹配；归档/恢复可验证 |
| 11 | 接口与集成 | 对内对外怎么契约化 | API 清单、请求/响应、错误码、鉴权、幂等、重试、第三方集成 | C4；Enterprise Integration Patterns（Hohpe/Woolf）；Context Mapping（ACL/OHS/PL）；API-first | 接口清单、集成契约、错误码表 | 每个接口有鉴权/幂等/错误语义 |
| 12 | 安全与横切 | 保护什么、失败怎么办、怎么观测 | 信任边界、凭据矩阵、越权处理、审计、STRIDE 威胁建模、可观测性三支柱、错误分类 | STRIDE；OWASP ASVS；最小权限/纵深防御/零信任；SRE（SLI/SLO/错误预算）；arc42 §8 Crosscutting | 安全/可观测/错误处理/配置密钥方案 | 每个威胁有控制与残留风险；SLO 有测量与失败表现 |
| 13 | 架构决策 | 为什么这样选、什么时候推翻 | ADR：背景/备选/决策/代价/推翻条件；ATAM 权衡点/敏感点 | ADR（Nygard）；MADR；ATAM（SEI） | 决策记录表 | 每条决策有备选、代价、推翻条件 |
| 14 | 质量与验证 | 怎么证明设计有效 | 质量属性场景、验收判据、架构测试/fitness function、压测、故障注入、对账 | ISO/IEC 25010；ATAM；SRE；fitness function（进化架构）；ArchUnit/Pact/Chaos Engineering | 追溯表、测试验收策略、验证报告 | 需求→设计→验收可追溯；关键场景有测试/监控证据 |
| 15 | 文档与评审 | 怎么让不同读者读懂、可维护 | 视图组织、图例/编号、权威顺序、修订史、评审角色 | IEEE 42010；arc42；4+1；C4；ATAM 评审 | 架构总览、图索引、评审报告 | 读者能按角色找到信息；评审问题闭环 |

## 2. 逻辑架构：展开步骤与依据

1. **定驱动因素**：从质量属性场景里挑 3–5 个（ATAM/ISO 25010）。
2. **切第一刀**：按业务能力/限界上下文（DDD），不按技术层。
3. **写模块六项**：名称/职责/接口/依赖/不做/承载需求（arc42 §5；C4 Component）。
4. **定依赖规则**：单向、无环、跨上下文走端口（Parnas 模块化；Clean Architecture）。
5. **选结构风格**：分层/六边形/模块化单体/微服务，写代价（4+1 Logical View）。
6. **场景验证**：每条用例走模块链，检查孤岛/环/跨层（4+1 Scenarios）。
7. **落文档**：模块图 + 表 + 接口目录 + 依赖矩阵（arc42 §5）。

## 3. 物理架构：展开步骤与依据

1. **映射部署单元**：逻辑块→进程/容器/Pod/函数，按扩缩容/故障/安全/团队边界决定合并拆分（4+1 Physical View；C4 Deployment）。
2. **划真实分区**：用户侧/入口/集群/数据/外部，必须是网络或信任边界（arc42 §7；UML Deployment）。
3. **画网络路径**：协议/端口/方向/出入口白名单（C4 Deployment；EIP）。
4. **定存储拓扑**：真源/副本/分片/缓存/对象存储/备份/RPO-RTO（可靠性理论；CAP）。
5. **定高可用与扩缩容**：副本/故障域/主节点切换/HPA 指标（可靠性；Kubernetes 模式）。
6. **定运维面**：探针/日志/指标/告警/容量（SRE）。
7. **场景验证**：单副本故障/主节点切换/缓存故障/供应商不可用/峰值，逐个走（ATAM 质量场景）。

## 4. 理论细节位置

agent 不需要联网：每个方法论的完整内容（定义/概念/步骤/产物/检查清单/误用/出处）在 `theories/` 目录。

| 理论 | 详细文件 |
|---|---|
| arc42 / 4+1 / C4 / IEEE 42010 / UML | `theories/01-views-and-documentation.md` |
| DDD | `theories/02-ddd.md` |
| ISO 25010 / ATAM / SRE / fitness function | `theories/03-quality-attributes.md` |
| ACID / CAP / PACELC / 幂等 / Outbox / Saga | `theories/04-consistency-and-messaging.md` |
| Parnas / Clean / Hexagonal / 包原则 / Conway | `theories/05-modularity-and-dependencies.md` |
| 可靠性 / 故障域 / RPO-RTO / 可观测 / K8s | `theories/06-reliability-and-deployment.md` |
| STRIDE / 信任边界 / OWASP / EIP / API 契约 | `theories/07-security-and-integration.md` |
| ADR / MADR / 决策质量 / ATAM 权衡 / 评审 | `theories/08-decisions-and-review.md` |

外部链接只用于溯源，写在每个详细文件的最后一节。
