# 架构终极进化路线图：4 阶段执行计划

> 日期: 2026-05-29 | 版本: v1.1 | 状态: 红队已修订
> 蓝图依据: `architecture-final-vision.md`
> 涉及: kairon, SharedBrain, agentmesh, gbrain, ops, SharedWork(10项目)

---

## 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-05-29 | 初版，4 阶段路线图 |
| **v1.1** | 2026-05-29 | 红队审查后修订：① memU兼容性预检提前到Sprint1 ② Phase2新增授权框架RBAC ③ Phase3-4从"自主"降级为"辅助自主"(Human-in-the-Loop) ④ EU经济增加外部锚定 ⑤ 风险评估增加8条 |

### 红队审查关键发现

| # | 发现 | 严重性 | 修订措施 |
|---|------|:---:|------|
| R1 | Docker是Phase1第一道坎(国内网络) | 🔴 | 风险表中标注为CRITICAL，Sprint1 W1首要任务 |
| R2 | memU兼容性是最大未知数 | 🔴 | **新增P1.3-PRE**: Sprint1就做兼容性探测，结果决定Sprint2是否继续 |
| R3 | Phase3-4自主能力是科幻 | 🔴 | **降级为"辅助自主"**: KOS推荐→人类确认→再生效。所有自主操作保留人工审核环节 |
| R4 | 一人维护5个异构项目 | 🔴 | 风险表标注为CRITICAL，每Phase要求文档完备度检查 |
| R5 | EU经济是循环论证 | 🟠 | **增加外部锚定**: EU成本参照真实API调用价格 |
| R6 | LiteLLM是外部不可控依赖 | 🟠 | 增加备选方案(LiteLLM不可达→agentmesh直连模型) |
| R7 | 无授权框架RBAC | 🟠 | **新增Phase2.5**: 授权框架，在Agent数量增长前建立安全边界 |
| R8 | 集成测试维护成本高 | 🟡 | Sprint3增加测试自动化脚本，降低维护成本 |

---

## 目录

1. [总体时间线](#一总体时间线)
2. [Phase 1: 基础设施补完](#二phase-1-基础设施补完)
3. [Phase 2: 知识能力深化](#三phase-2-知识能力深化)
4. [Phase 3: 自我进化闭环](#四phase-3-自我进化闭环)
5. [Phase 4: 自主运行](#五phase-4-自主运行)
6. [整体治理框架](#六整体治理框架)
7. [复盘问题库](#七复盘问题库)
8. [整体风险评估](#八整体风险评估)

---

## 一、总体时间线

```
2026 Q2 ─────── Q3 ─────── Q4 ─────── 2027 Q1 ─────── Q2 ─────── Q3+
  │              │              │              │              │
  ├─ Phase 1 ────┤              │              │              │
  │  基础设施补完 │              │              │              │
  │  (4-6 周)    │              │              │              │
  │              ├─ Phase 2 ────┤              │              │
  │              │  知识能力深化 │              │              │
  │              │  (6-8 周)    │              │              │
  │              │              ├─ Phase 3 ────┤              │
  │              │              │  自我进化闭环 │              │
  │              │              │  (8-12 周)   │              │
  │              │              │              ├─ Phase 4 ────┤
  │              │              │              │  自主运行      │
  │              │              │              │  (持续)       │
```

| 阶段 | 时长 | 新增 kairon 包 | 融入 SharedWork | 系统健康目标 |
|------|:----:|:--------------:|:---------------:|:------------:|
| Phase 1 | 4-6 周 | +2 (sharedbrain-bridge) | 3 项目 (LiteLLM, memU, sharedbrain) | 75/100 |
| Phase 2 | 6-8 周 | +3 (GitNexus, Graphify, UltraRAG) | 5 项目 | 82/100 |
| Phase 3 | 8-12 周 | +2 (MinerU, nuwa-skill) | 2 项目 | 88/100 |
| Phase 4 | 持续 | 持续 | 持续 | 91/100 |

---

## 二、Phase 1: 基础设施补完

> **时间**: 2026 Q2-Q3 (4-6 周)
> **目标**: 4 个核心系统全部就位，开始协同工作。kairon 和 SharedBrain 整合完成。agentmesh 获得 LLM 路由能力。gbrain 获得高性能记忆。

### 2.1 蓝图

```
Phase 1 目标态:
┌──────────────────────────────────────────────────────┐
│                                                    │
│  kairon (19 包)        SharedBrain (14 器官)        │
│  ┌─────────────┐       ┌──────────────┐            │
│  │ sharedbrain- │◄────►│ 合规控制面   │            │
│  │ bridge (EU   │ Agora│ EU·免疫·身份 │            │
│  │ 计价+免疫+   │       │ ·自愈·语音   │            │
│  │ 同步)        │       │ 4 delegated  │            │
│  └─────────────┘       └──────────────┘            │
│                                                    │
│  agentmesh (+LiteLLM)    gbrain (+memU)            │
│  ┌──────────────┐       ┌──────────────┐           │
│  │ LLM 智能路由  │       │ Rust 记忆核心 │           │
│  │ 配额·回退·    │       │ Postgres     │           │
│  │ 25+ Agent     │       │ 74 MCP tools │           │
│  └──────────────┘       └──────────────┘           │
│                                                    │
│                  Agora (100+ MCP)                   │
│            全链路 MCP 连通性验证通过                  │
│                                                    │
└──────────────────────────────────────────────────────┘
```

### 2.2 任务拆解

#### P1.1 — kairon × SharedBrain 整合完成 (1-2 周)

| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P1.1a | 完成 Phase A-0/A/B/C 遗留：Docker 集成测试 | PM | docker-compose.yml | `docker compose up` 全服务 healthy | 5/5 服务健康 |
| P1.1b | sharedbrain-bridge 包完成（EU 计价 + 免疫审计 + 批量同步） | kairon | Phase C 已建文件 | 包可 pip install + 5 MCP tools | 5/5 工具注册到 Agora |
| P1.1c | 端到端验证：kairon → Agora → SharedBrain → Agora → kairon | QA | 烟雾测试 | 全链路 6/6 测试 PASS | 含 3 个故障场景 |
| P1.1d | B3b: SSOT 最终 organ 状态同步完成 | kairon | C1 delegated 器官 | SSOT organ 状态与 SharedBrain 一致 | SHA-256 指纹匹配 |

#### P1.2 — agentmesh 吸收 LiteLLM LLM 路由 (2 周)

| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P1.2a | LiteLLM 独立部署 + 配置（100+ 模型支持） | Infra | LiteLLM repo | Docker 运行，可路由 3+ 模型 | API 调用返回正确模型响应 |
| P1.2b | agentmesh Gateway 增加 LiteLLM 路由适配器 | agentmesh | LiteLLM API | Gateway 通过 LiteLLM 分发 LLM 请求 | 3 种模型自动路由+回退 |
| P1.2c | 配额管理 + 成本追踪 + 回退链配置 | agentmesh | LiteLLM | 配额超限 → 回退 → 日志 | 配额 0 → 回退到免费模型 |
| P1.2d | agentmesh 注册 LiteLLM 相关 MCP 工具到 Agora | agentmesh | agentmesh MCP | Agora registry 新增 5+ LLM 路由工具 | `agora registry list` 确认 |

#### P1.3-PRE — ⚠️ memU 兼容性预检 (Phase 1 启动即执行)

> **关键决策点**: 此任务决定 P1.3 (gbrain memU 迁移) 是否继续。
> 如果兼容性 <60/74 tools，P1.3 跳过，进入 Plan B (仅编译 memU 库，不迁移)。

| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P1.3-pre1 | memU Rust 核心编译 (macOS) | gbrain | memU repo | `.dylib` 动态库 | `file` 确认架构 |
| P1.3-pre2 | 创建兼容性测试脚本 (无需全部 gbrain 74 tools 运行，用测试桩) | gbrain | memU .dylib | 兼容性报告 (X/74 tools) | ≥60 → GO, <60 → NO-GO |
| P1.3-pre3 | 决策: memU 迁移 GO / NO-GO | PM | 兼容性报告 | 决策日志 → .omo/decisions/ | 决策已记录 |

#### P1.3 — gbrain 吸收 memU 记忆核心 (2 周，取决于 P1.3-PRE GO)


| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P1.3a | memU Rust 核心编译为动态库 | gbrain | memU repo | `.so/.dylib` 被 gbrain 加载 | `ldd` / `otool` 确认 |
| P1.3b | gbrain 增加 memU 记忆后端（替代/补充现有 SQLite） | gbrain | memU .so | 记忆写入/查询走 memU | 延迟 < 50ms (P99) |
| P1.3c | 迁移现有 gbrain 记忆数据到 memU | gbrain | 现有 SQLite | memU 中包含历史记忆 | 数据完整性检查通过 |
| P1.3d | 性能基线：memU vs SQLite 对比 | gbrain | 两种后端 | 基准报告 | memU 延迟 < SQLite × 0.5 |

#### P1.4 — Phase 1 整体验证 (1 周)

| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P1.4a | 全系统集成测试：kairon→SB→agentmesh→gbrain→Agora | QA | 4 系统 | 端到端测试 10+ 用例 PASS | 100% 通过 |
| P1.4b | 性能基线：跨系统 MCP 调用延迟 | QA | 各系统 | 延迟报告 | P99 < 200ms |
| P1.4c | 架构合规检查（10 条法则） | Arch | .omo/ | 合规报告 | 0 条违规 |
| P1.4d | 文档更新：CONVERGENCE.yaml + LAYER-INDEX.md | Doc | 变更 | 更新文档 | 一致性检查 |

### 2.3 里程碑

| M1.1 | 第 2 周末 | kairon × SharedBrain 整合完成 + 烟雾测试 6/6 PASS |
| M1.2 | 第 4 周末 | agentmesh LLM 路由就绪 + gbrain memU 就绪 |
| M1.3 | 第 5 周末 | 全系统集成测试 10/10 PASS + 架构合规 0 违规 |
| **M1.GO** | **第 6 周末** | **Phase 1 Go/No-Go: 提交验收报告** |

### 2.4 验收标准

- [ ] Docker Compose 5 服务全部 healthy
- [ ] CI 管道: 单元测试 + 构建 + 集成测试 全部通过
- [ ] 全系统 MCP 连通性: kairon→SB→agentmesh→gbrain 全链路
- [ ] agentmesh Gateway 通过 LiteLLM 路由到 3+ 模型
- [ ] gbrain 记忆写入/查询延迟 < 50ms (P99)
- [ ] 架构合规: 10 条法则 0 违规
- [ ] 系统健康评分 ≥ 75/100（从 66.80 提升）
- [ ] SharedBrain 16,676 测试 + kairon 测试 + agentmesh 测试 + gbrain 测试 全部通过

### 2.5 复盘问题

Phase 1 结束后必须回答：

1. SharedBrain × kairon 整合有没有引入新的循环依赖或紧耦合？
2. agentmesh + LiteLLM 的延迟开销是多少？是否影响 Agent 体验？
3. memU 替代 SQLite 后，gbrain 的 74 个 MCP 工具是否全部兼容？
4. 有没有哪个集成点可以更简单？哪个是过度工程？
5. 实际耗时 vs 预估耗时的偏差原因是什么？
6. 开发体验：在 4 个项目间切换是否顺畅？uv workspace / bun workspace 够用吗？
7. 测试环境搭建是否自动化足够？新人能 `git clone && make test-all` 吗？
8. 架构法则有没有被违反？如果有，为什么？法则需要修改吗？

---

## 三、Phase 2: 知识能力深化

> **时间**: 2026 Q3-Q4 (6-8 周)
> **目标**: kairon 知识管线到达行业领先水平。KOS 吸收代码图谱和文档图谱。minerva 获得 RAG 增强和自主研究能力。kronos 集成高精度文档解析。

### 3.1 蓝图

```
Phase 2 目标态:
┌──────────────────────────────────────────────────────┐
│                                                    │
│  KOS 知识操作系统 (L3 → 增强 L4 self + X3 价值)     │
│  ┌──────────────────────────────────────────────┐   │
│  │ KOS self: nuwa-skill → 自主技能生成          │   │
│  │ KOS collab: 多 Agent 知识共识               │   │
│  │ KOS index: ← GitNexus(代码图谱) ← Graphify(文档图谱)│
│  │ KOS ingest: pipeline:json 增量索引流水线      │   │
│  └──────────────────────────────────────────────┘   │
│                                                    │
│  minerva 深度研究 → 行业领先                        │
│  ┌──────────────────────────────────────────────┐   │
│  │ UltraRAG: 检索增强生成框架                    │   │
│  │ AgentLaboratory: 自主研究 → 论文撰写          │   │
│  │ ImmuneAudit: SharedBrain 免疫审计             │   │
│  │ EUPricing: 每次研究消耗计费                   │   │
│  └──────────────────────────────────────────────┘   │
│                                                    │
│  kronos 摄取管线 → 全格式覆盖                        │
│  ┌──────────────────────────────────────────────┐   │
│  │ MinerU: 高精度 PDF/文档解析                   │   │
│  │ Firecrawl MCP: 网页智能抓取                   │   │
│  │ RSS/Atom feed: 持续摄取                       │   │
│  └──────────────────────────────────────────────┘   │
│                                                    │
│  EU 经济全系统化 + 免疫全系统化                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ 每个 MCP 调用 → EU 消耗 → 余额不足 → 402     │   │
│  │ 每个知识写入 → 免疫审计 → HIGH风险 → 标记     │   │
│  └──────────────────────────────────────────────┘   │
│                                                    │
└──────────────────────────────────────────────────────┘
```

### 3.2 任务拆解

#### P2.1 — KOS 吸收知识图谱能力 (3 周)

| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P2.1a | GitNexus 代码图谱融入 KOS index | kairon/KOS | GitNexus API | KOS 可索引代码仓库 → Entity/Relation | 3 个仓库成功索引 |
| P2.1b | Graphify 文档图谱融入 KOS index | kairon/KOS | Graphify CLI | KOS 可索引文档 → 知识关系图 | 10 篇文档成功索引 |
| P2.1c | KOS 跨域检索：代码 + 文档 + 知识统一搜索 | kairon/KOS | 2 个图谱 | 统一检索 API → 混合结果 | 查询返回 3 域结果 |
| P2.1d | KOS 知识共识机制（多 Agent 投票） | kairon/KOS | collab | 多 Agent 对知识卡片置信度投票 | 3 Agent 共识测试 |

#### P2.2 — minerva 研究增强 (2 周)

| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P2.2a | UltraRAG 融入 minerva retrieval pipeline | kairon/minerva | UltraRAG | minerva 搜索结果质量提升 | 召回率 +15% |
| P2.2b | AgentLaboratory 自主研究模式 | kairon/minerva | AgentLab | minerva 可自主设计实验 → 执行 → 撰写 | 1 篇自主生成论文 |
| P2.2c | minerva pipeline:json 增加 ImmuneAudit + EUPricing 阶段 | kairon/minerva | Phase C 代码 | 每次研究自动审计+计费 | 端到端管道测试 |

#### P2.3 — kronos 全格式摄取 (2 周)

| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P2.3a | MinerU 集成到 kronos 文档解析层 | kairon/kronos | MinerU Docker | kronos 支持高精度 PDF/Word/PPT 解析 | 复杂 PDF（表格+图）正确提取 |
| P2.3b | Firecrawl MCP 集成到 kronos 抓取层 | kairon/kronos | Firecrawl MCP | kronos 4 层管道第 1 层使用 Firecrawl | 动态网页正确抓取 |
| P2.3c | SSD/向量数据库存储摄取产物 | kairon/kronos | LanceDB/Qdrant | 管道产物持久化 + 检索 | 向量搜索延迟 < 50ms |
| P2.3d | cron-service 定时摄取流水线 | kairon | kronos | 每小时自动扫描 RSS/Atom → 入管道 | 24h 自动运行验证 |

#### P2.4 — EU 经济 + 免疫全系统化 (1-2 周)

| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P2.4a | Agora EU 路由中间件（仅路由，不计算） | kairon/Agora | eu-pricing | 每个 MCP 调用 → 检查 EU → 不够 → 402 | 余额不足时正确拒绝 |
| P2.4b | agentmesh → EU 计价集成 | agentmesh | eu-pricing | agentmesh 每次工具调用消耗 EU | Agent 日志显示 EU 消耗 |
| P2.4c | gbrain → EU 计价集成 | gbrain | eu-pricing | gbrain 每次记忆写入消耗 EU | 记忆操作日志显示 EU |
| P2.4d | 免疫审计接入 kronos 和 agentmesh | kairon/minerva | immune_audit | 外部数据摄入前审计 + Agent 输出审计 | 高风险内容正确拦截 |

#### P2.5 — 授权框架 RBAC (1-2 周，Phase 2 新增)

> **背景**: 红队审查发现系统无授权机制。100+ MCP tools 任何人都能调用。在 Phase 3 的辅助自主能力启动前，必须先建立安全边界。

| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P2.5a | 定义 RBAC 模型：角色 (Admin/User/Agent/ReadOnly) + 权限矩阵 | Arch | 100+ MCP tools | RBAC 设计文档 | 团队审查通过 |
| P2.5b | Agora 中间件：每个 MCP 调用 → 检查 caller 角色 → 放行/拒绝 | kairon/Agora | RBAC 设计 | `auth_middleware.py` | 无权限调用 → 403 |
| P2.5c | agentmesh Agent 权限绑定：新建 Agent → 分配最小权限 | agentmesh | RBAC 设计 | Agent 创建时绑定角色 | Agent 越权调用被拒 |
| P2.5d | 权限审计日志：所有被拒绝的调用记录到日志 | kairon/Agora | T2.5b | 审计日志 → ops 数据库 | 可回溯查询 |

### 3.3 里程碑

| M2.1 | 第 3 周末 | KOS 双图谱索引就绪 + 统一检索可用 |
| M2.2 | 第 5 周末 | minerva 辅助研究能力就绪 + 授权框架就绪 |
| M2.3 | 第 7 周末 | kronos 全格式摄取 + EU 经济全系统化 |
| **M2.GO** | **第 8 周末** | **Phase 2 Go/No-Go: 知识管线行业领先 + 安全就绪** |

### 3.4 验收标准

- [ ] KOS 可索引 3+ 代码仓库 + 10+ 文档，统一检索延迟 < 500ms
- [ ] minerva 辅助研究：人工确认后再入库，生成至少 1 篇研究论文
- [ ] kronos 支持 PDF/Word/PPT/HTML/RSS 全格式摄取
- [ ] EU 经济覆盖 100% MCP 调用（kairon + agentmesh + gbrain），**EU 成本参照真实 API 价格**
- [ ] 免疫审计拦截率 > 80%（已知高风险内容）
- [ ] **授权框架就绪：Admin/User/Agent/ReadOnly 4 角色 + Agora 强制执行**
- [ ] 系统健康评分 ≥ 82/100
- [ ] 集成测试覆盖率 > 50%

### 3.5 复盘问题

1. KOS 双图谱索引的维护成本如何？是否需要专人维护 schema 映射？
2. minerva 自主研究的质量 vs 人工研究的质量差距多大？
3. MinerU 解析精度是否满足下游推导需求？
4. EU 经济是否造成了意外的熔断（余额正常但被拒绝）？
5. 免疫审计的误报率是多少？是否过于激进？
6. Agora 是否成为瓶颈？延迟中位数和 P99 是多少？
7. 有没有哪个融入的 SharedWork 项目实际价值不如预期？
8. 开发者体验：新包 `pip install` / `bun install` 是否顺畅？

---

## 四、Phase 3: 辅助自主决策闭环

> **时间**: 2026 Q4 - 2027 Q1 (8-12 周)
> **目标**: 系统具备辅助自主能力——KOS 推荐 Skill/Schema/Tool，**人类确认后再生效**。器官自愈全系统化。wksp:// URI 统一寻址。辅助自主研究管线。

### 4.1 蓝图

```
Phase 3 目标态:
┌──────────────────────────────────────────────────────┐
│                                                    │
│  KOS self: 自我进化能力                              │
│  ┌──────────────────────────────────────────────┐   │
│  │ nuwa-skill 融入 → 自主蒸馏人物思维框架        │   │
│  │ 自主发现新模式 → 生成新 Schema → 注册到 eidos   │   │
│  │ 自主发现新工具 → 生成 MCP tool → 注册到 Agora   │   │
│  │ 自主优化自身 prompt → A/B 测试 → 选择最优      │   │
│  └──────────────────────────────────────────────┘   │
│                                                    │
│  器官自愈全系统化                                    │
│  ┌──────────────────────────────────────────────┐   │
│  │ forge/entropy: 监控 kairon 服务 + agentmesh   │   │
│  │ D-Genesis: 自动重启/修复/回滚                 │   │
│  │ 自愈日志: 每次自愈 → 记录 → 分析 → 改进规则    │   │
│  └──────────────────────────────────────────────┘   │
│                                                    │
│  wksp:// URI 统一资源寻址                            │
│  ┌──────────────────────────────────────────────┐   │
│  │ wksp://minerva/research → agora → minerva MCP │   │
│  │ wksp://sharedbrain/immunity/audit → SB MCP    │   │
│  │ wksp://agentmesh/tools/run → agentmesh MCP    │   │
│  │ Agora registry = 唯一路由表                   │   │
│  └──────────────────────────────────────────────┘   │
│                                                    │
│  全自动研究管线 (pipeline:json v2)                    │
│  ┌──────────────────────────────────────────────┐   │
│  │ 触发 → 摄取 → 研究 → 推导 → 审计 → 索引 → 入库 │   │
│  │  cron 定时触发 或 Agent 自主触发               │   │
│  │  全程 EU 计价 + 免疫审计 + 日志追踪            │   │
│  └──────────────────────────────────────────────┘   │
│                                                    │
└──────────────────────────────────────────────────────┘
```

### 4.2 任务拆解

#### P3.1 — KOS self 自我进化 (4 周)

| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P3.1a | nuwa-skill 融入 KOS self | kairon/KOS | nuwa-skill | KOS 可调用 nuwa-skill 蒸馏人物思维框架 | 生成 3 个新人物 Skill |
| P3.1b | KOS 自主发现新模式：从知识图谱中提取新模式 → 生成 eidos Schema | kairon/KOS | KOS index | eidos 新增 5+ 自动生成 Schema | Schema 通过 eidos validate |
| P3.1c | KOS 自主发现新工具：分析 Agent 需求 → 生成 MCP tool → 注册 Agora | kairon/KOS | agentmesh | Agora 新增 5+ 自动生成工具 | 工具通过 Agora registry validate |
| P3.1d | KOS prompt 自优化：A/B 测试 → 选择最优 → 写入知识库 | kairon/KOS | minerva | prompt 质量指标提升 | 响应质量 +10% |

#### P3.2 — 器官自愈全系统化 (3 周)

| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P3.2a | forge/entropy 扩展监控范围：kairon 服务 + agentmesh | kairon/forge | entropy rules | 监控 10+ 服务健康 | 任一服务异常 → 告警 |
| P3.2b | D-Genesis 自愈规则扩展：自动重启 + 回滚 + 通知 | SharedBrain | forge entropy | 异常 → 自愈 → 恢复 → 日志 | 5 次模拟异常 5 次成功自愈 |
| P3.2c | 自愈学习：从自愈日志中提取模式 → 改进规则 | SharedBrain | 自愈日志 | 规则自动优化 | 误报率下降 |
| P3.2d | 自愈仪表盘：Agora Dashboard 显示自愈历史和统计 | kairon/Agora | 自愈数据 | 可视化仪表盘 | Dashboard 可查看 |

#### P3.3 — wksp:// URI 统一寻址 (2 周)

| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P3.3a | Agora registry 增加 URI 映射层 | kairon/Agora | registry.yaml | `wksp://domain/tool → mcp://host:port` | 100% 工具有 wksp:// URI |
| P3.3b | 所有 CLI (wksp/gstack/bos/pallas) 迁移到 wksp:// URI | CLI | wksp:// | 统一入口 | 命令输出一致 |
| P3.3c | IDE 插件支持 wksp:// URI | agentmesh | wksp:// | Cursor/Codex 可直接调用 | 插件安装 + 调用成功 |
| P3.3d | URI 文档自动生成：Agora Dashboard 显示所有 wksp:// URI | kairon/Agora | registry | 交互式 URI 目录 | Dashboard 可浏览 |

#### P3.4 — 全自动研究管线 (3 周)

| ID | 任务 | 负责 | 输入 | 输出 | 验收 |
|----|------|------|------|------|------|
| P3.4a | pipeline:json v2 协议定义 | kairon/eidos | v1 | 新协议 Schema | eidos validate 通过 |
| P3.4b | 管线编排器：Agora pipeline 支持条件分支和并行 | kairon/Agora | pipeline | 复杂 DAG 管线执行 | 并行分支结果正确合并 |
| P3.4c | 自动触发：cron + Agent 事件 → 管线启动 | kairon/cron | 管线 | 24h 自动运行 | 连续 72h 无故障 |
| P3.4d | 全自动研究 → 知识卡片 → KOS index | 全系统 | 管线 | 知识自动入库 | 日均 10+ 卡片入库 |

### 4.3 里程碑

| M3.1 | 第 4 周末 | KOS self 可自主生成 Skill + Schema + Tool |
| M3.2 | 第 7 周末 | 全系统自愈 + wksp:// URI 统一 |
| M3.3 | 第 10 周末 | 全自动研究管线 72h 无人值守 |
| **M3.GO** | **第 12 周末** | **Phase 3 Go/No-Go: 自我进化闭环** |

### 4.4 验收标准

- [ ] KOS 自主生成 ≥ 3 个 Skill + ≥ 5 个 Schema + ≥ 5 个 MCP Tool
- [ ] 自愈成功率 ≥ 90%（20 次模拟异常，18 次成功自愈）
- [ ] wksp:// URI 覆盖 100% MCP 工具
- [ ] 全自动研究管线 72h 连续运行，零故障
- [ ] 日均自动入库知识卡片 ≥ 10
- [ ] 系统健康评分 ≥ 88/100

### 4.5 复盘问题

1. KOS 自动生成的 Schema/Tool 质量如何？有多少被人工回退？
2. 自愈系统是否引入了新的故障模式（修复 A 破坏 B）？
3. wksp:// URI 是否被开发者接受？有无未预料的使用场景？
4. 全自动研究管线的知识质量 vs 半自动（有人工审核）差距多大？
5. 系统自主演化方向是否符合预期？是否需要限速或护栏？
6. EU 经济是否导致系统自我限制（为省 EU 而降低研究质量）？
7. 有没有出现不可预见的架构违规？
8. 开发者体验：新人上手需要多长时间？

---

## 五、Phase 4: 高自主运行 (Human-in-the-Loop)

> **时间**: 2027 Q2+ (持续)
> **目标**: 系统在日常操作中 > 80% 自主执行，但关键决策保留人工审核环节。可自愈、可辅助进化、可分发。

### 5.1 蓝图

```
Phase 4 目标态:
┌──────────────────────────────────────────────────────┐
│                                                    │
│  ██ 高自主运行 (High Autonomy + Human-in-the-Loop) ██  │
│                                                    │
│  ◆ Agent 高自主执行: 研究→推导→索引→入库 自动完成   │
│    但新 Skill/Tool 生成 → KOS 推荐 → 人类确认 → 生效  │
│  ◆ KOS 辅助进化: 发现新模式 → 推荐给人类 → 确认后吸收  │
│  ◆ EU 经济闭环: 自给自足 + 外部价格锚定              │
│  ◆ 免疫辅助: 发现漏洞 → 推荐修复方案 → 人类确认       │
│  ◆ 系统可分发: Omostation 可分发给其他用户           │
│                                                    │
│  人类角色: 审核新 Skill/Schema/Tool + 处理异常 + 设定目标│
│                                                    │
└──────────────────────────────────────────────────────┘
```

### 5.2 目标（非任务，持续迭代）

| 目标 | 描述 | 衡量 |
|------|------|------|
| **辅助自主率** | 系统推荐+人类确认完成的决策比例 | > 80% 操作有 AI 推荐 |
| **准确率** | 辅助推荐的正确率 | > 95% 推荐被接受 |
| **自愈率** | 异常自动恢复比例 | > 95% |
| **进化速度** | 辅助发现新模式/新能力的速度 | > 1 推荐/周 |
| **分发度** | 系统可被新用户安装并运行 | `git clone && make up` 1 次成功 |
| **健康评分** | 8 维度系统健康 | ≥ 91/100 |

### 5.3 里程碑

| M4.1 | Q2 2027 | 辅助自主率 > 50% |
| M4.2 | Q3 2027 | 辅助自主率 > 70% |
| M4.3 | Q4 2027 | 辅助自主率 > 80% + 可分发给 3+ 用户 |
| **M4.GOAL** | **持续** | **系统可运行数周，仅需人工审核关键决策** |

---

## 六、整体治理框架

### 6.1 决策机制

| 决策类型 | 决策者 | 速度 | 可逆 |
|---------|--------|:----:|:----:|
| 架构法则修改 | 架构委员会 (Oracle + RedTeam) + 人类确认 | 慢 | 否 |
| 新 SharedWork 项目融入 | 架构委员会 | 中 | 可 |
| Phase 任务优先级调整 | PM (人类) | 快 | 可 |
| 技术选型 (库/框架) | 开发者 + Oracle 审查 | 快 | 可 |
| Bug 修复 | 开发者 | 极快 | 可 |

### 6.2 质量门禁

每个任务完成后必须通过：

1. **LSP 诊断**: 0 新错误
2. **单元测试**: 覆盖率不下降
3. **集成测试**: 相关场景 PASS
4. **架构合规**: 10 条法则 0 违规（自动检查）
5. **代码审查**: 至少 1 个 AI Agent (Sisyphus/Momus) 审查通过

每个 Phase 完成后必须通过：

1. **全系统集成测试**: 20+ 用例 PASS
2. **性能基线**: 延迟 ≤ 基线 × 1.2
3. **架构审计**: Oracle 审计通过
4. **安全扫描**: 无 CRITICAL/HIGH 漏洞
5. **复盘报告**: 8 个复盘问题已书面回答

### 6.3 工具链

| 用途 | 工具 |
|------|------|
| Python 构建/测试 | uv + pytest + ruff |
| TypeScript 构建/测试 | bun + vitest |
| 集成测试 | Docker Compose + pytest |
| 架构合规 | arcnode (待实现) |
| 性能监控 | Agora metrics + Prometheus |
| 健康评分 | .omo 健康矩阵 |
| 代码审查 | Sisyphus/Momus |
| 文档 | .omo/ 目录 |

---

## 七、复盘问题库

### 每 Phase 通用复盘

1. **目标达成**: 计划 vs 实际？偏差原因？
2. **架构健康**: 有没有架构法则被违反？法则需要修改吗？
3. **技术债务**: 跳过了什么？需要何时补？
4. **人员瓶颈**: 有没有单点知识依赖（只有一个人懂某个模块）？
5. **开发体验**: 新人上手要多久？CI 反馈速度够快吗？
6. **质量趋势**: 测试覆盖率上升还是下降？Bug 率上升还是下降？

### 跨 Phase 战略复盘 (每半年)

1. **方向正确吗**: 终极蓝图是否需要调整？
2. **优先级对吗**: 下一个 Phase 的目标是否仍然是最重要的？
3. **SharedWork 还有未发掘的宝藏吗**: SharedWork 中新克隆/开发的项目是否应该融入？
4. **外部变化**: AI 行业的新趋势（新模型、新协议、新范式）是否影响我们的方向？
5. **资源充足吗**: 人类时间、AI Agent 能力、计算资源是否够用？
6. **用户反馈**: 如果系统已被使用，用户的核心痛点是什么？

---

## 八、整体风险评估

| 风险 | 影响 | 概率 | 缓解 |
|------|:----:|:----:|------|
| **SharedWork 项目代码质量低**（融入时需大量重写） | 高 | 中 | 融入前先做代码审查；只吸收 API/设计，重写实现 |
| **kairon Python 版本限制**（3.10 vs 新库要求 3.12+） | 中 | 中 | Phase 1 升级 kairon → 3.12 |
| **agentmesh × gbrain TypeScript 版本不一致** | 中 | 低 | bun 统一管理 |
| **Agora 成为性能瓶颈**（100+ MCP 工具路由） | 高 | 低 | 水平扩展 Agora + 本地缓存 |
| **EU 经济过激**（余额不足导致系统停摆） | 高 | 中 | EU 默认余额充足 + 管理员免检模式 |
| **免疫审计误杀**（正常内容被拦截） | 中 | 中 | 人工审核队列 + 白名单机制 |
| **KOS 自主进化不可控**（生成低质量 Schema/Tool） | 中 | 中 | 人工审核 + 沙箱测试 + 回滚机制 |
| **开发者流失**（只有 1 人维护整个系统） | 致命 | 高 | 文档完备 + AI Agent 可接手 + 开源社区 |
| **架构腐败**（随时间推移法则被忽视） | 致命 | 中 | 自动化架构合规检查 + Phase 关卡 |

---

## 附录: Phase 依赖关系和并行机会

```
Phase 1 ────────→ Phase 2 ────────→ Phase 3 ────────→ Phase 4

Phase 1 内部:
  P1.1 (kairon×SB)  ──→ (并行) ── P1.2 (agentmesh) ── P1.3 (gbrain)

Phase 2 内部:
  P2.1 (KOS图谱)    ──→ (并行) ── P2.2 (minerva) ── P2.3 (kronos)
       └──→ (P2.1 + P2.2 完成后) ──→ P2.4 (EU经济全系统化)

Phase 3 内部:
  P3.1 (KOS self)   + P3.3 (wksp://) → 可并行
  P3.2 (自愈)  依赖 P1.1 + P2.1 + P2.2
  P3.4 (全自动管线) 依赖 P2.2 + P2.3 + P3.1
```

---

> **文档版本**: v1.1 | **下次复审**: Phase 1 结束后 | **负责人**: PM + Oracle
> **红队审查**: 已完成（8 条关键发现已纳入修订）
