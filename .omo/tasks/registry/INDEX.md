# Tasks Registry — 结构化任务注册表

> 替代 system.yaml 中的 orphaned_tasks blob。
> 每个任务有独立 YAML 文件。system.yaml 只保留指针引用。
> **SSOT**: 任务文件在 `tasks/` 下。本文档由验证流程生成,与实际目录保持同步。

## Active Tasks

当前无活跃任务。所有 in-progress 任务通过 `.omo/tasks/planned/` 排队等待认领。

## Planned Tasks (47 个)

P33 战役 (Phase 33): BOS URI + 3 战役

| ID | Title |
|----|-------|
| P33-STARTUP-EVAL | P33 启动评估 — 3 战役可行性 + 建首批 3 任务 |
| P33-W0-FOLD | 归档 P30/P31/P32 — 让 planned/ 平面只剩 P33 |
| P33-W0-NORTH-STAR | P33 北极星 — 人类审批 5 Domain + BOS URI 战略 |
| P33-W1-CAMPAIGN-2-PRECHECK | 战役 2 前置: 5 Domain 边界 + BOS URI 命名约定 |
| P33-W2-DOMAINS-3 | 战役 2 余下 3 Domain — Analysis + Persona + Capability |
| P33-W3-FIX | 修 3 高严重度 — KOS 持久化 + 实测可达 + 命名 |
| P33-W4-AGORA-MESH | 战役 1: agora BOS URI 解析器 + kairon stdio MCP server |
| P33-W5-FORGE-MARKET | 战役 3: forge 集市 + 工具热加载 |
| P33-VERIFY | P33 验收 — 6 wave 全完成, 21 BOS URI 真活 |

P34 战役 (Phase 34): URI 扩展 + stdio 生产化

| ID | Title |
|----|-------|
| P34-W0-URI-EXPAND | 战役 2 扩展 — 21 → 40 URI (5 Domain 细分) |
| P34-W1-AGORA-W4-UPGRADE | agora spawn 升级 — W4 POC 到生产 stdio MCP 协议 |
| P34-W2-ANALYSIS-EXEC | Analysis 域 12 URI 实战化验证 — 真实 stdio 串联 |
| P34-W3-MULTI-REPO-RELEASE | 多仓库统一版本发布 — release.sh + CHANGELOG + VER |
| P34-W4-FIX-AUDIT | 修任务 YAML 描述债务 — audit 95→100 (A+ 恢复) |
| P34-W5-REAL-SCENARIO | 真实场景 5/5 ok — 修基础设施让 5 URI 串联全通 |
| P34-VERIFY | P34 验收 — 6 wave 全完成, 40 URI 真活, 5/5 真实场景 |

P35-P54 战役 (合并实施)

| ID | Title |
|----|-------|
| P35-ROADMAP | Phase 35 战略路线图 |
| P35-W0-DOMAIN-CHAIN | 跨 Domain 串联 — 5 场景验证 |
| P35-W1-W2-COMBO | 战役 4 spawn 真替代 + CI 集成 omo audit |
| P35-W3-FIX-AUDIT | 修 P35 任务 YAML 描述债务 — audit 100 |
| P35-VERIFY | P35 验收 — 4 wave, 跨域 9/11 ok, audit 100 |
| P36-W0-W1-COMBO | 治理债务永久化 + 跨域 GAP 补 |
| P36-W2-W3-COMBO | 观测性落地 + P36 验收 |
| P37-W0-W1-COMBO | CI workflow 真启用 + 治理历史清仓 |
| P37-W2-W3-COMBO | 跨域+LLM 实战 + P37 验收 |
| P38-W0-W1-COMBO | CI 真触发 + 跨域 LLM 真调用 |
| P38-W2-W3-COMBO | 观测性 dashboard + P38 验收 |
| P39-W0-W1-COMBO | GitHub push 真启用 + 跨域+LLM 真消费卫健委场景 |
| P39-W2-W3-COMBO | dashboard 真服务化 + P39 验收 |
| P40-W0-W1-COMBO | GitHub 真启用 (gh CLI) + LLM 真 anthropic |
| P40-W2-W3-COMBO | dashboard 持续服务化 + P40 验收 |
| P41-W0-W1-COMBO | LLM 用 ollama + 修 GitHub workflow failure |
| P42-W0-W1-COMBO | audit 守回 100.0 + P41 收尾 |
| P42-W2-COMBO | agora 跨进程 URI 派发闭环 |
| P43-W0-W3-COMBO | P43 4 wave 全面实施 |
| P44-W0-W4-COMBO | P44 5 wave 全面实施 |
| P45-W0-W3-COMBO | P45 战役 1 — 10 GAP URI 实施 |
| P45-W0-DESIGN-REGISTER | BOS URI 理想态架构设计与 L0 注册 |
| P45-W1-P0-BLOCKER-FIX | P0 阻断修复 — Agent 能通过 BOS URI 访问系统 |
| P45-W2-UNIFIED-ROUTING | P1 统一路由 — 合并双表 + 通配注册 + 统一错 |
| P45-W3-GOVERNANCE-SCHEMA | P2 治理 + Schema — 鉴权/审计/Schema 契约 |
| P46-W0-RELIABILITY | BOS 可靠性 — 限流/熔断/缓存 |
| P54-W0-MCP-STDIO-MIGRATION | POC 自定义协议 → 标准 MCP stdio JSON-RPC 2.0 迁移 |
| P54-W1-TEAM-REVIEW | 团队 Review — P33→P53 全量成果评审 |

OPC (Open Controller / Persistent Compute) 计划任务

| ID | Title |
|----|-------|
| OPC-PHASE-PLAN | OPC personal swarm AI brain roadmap |
| OPC-P2-MEMORY-SPINE | ~~OPC-P2: Personal Memory Spine~~ **已完工,待迁至 done/** |
| OPC-P3-SWARM-SPINE | OPC-P3: Swarm Execution Spine |
| OPC-P15-KAI-01 | kairon JSONL write path audit and schema check hardening |

## Completed Tasks (167 个)

> `tasks/done/` — 167 YAML files across Phases 0-32.

全部已完成 Phase 列表:
Phase 0-7, Phase 8-24, Phase 25-32. 详见 `tasks/done/` 子目录。

关键完成里程碑:
- Phase 3-16 — 全量完成
- P17-W1/2/3/4 — Architecture foundation + protocols v1 + gap analysis + agentmesh audit
- P18-W1/2/3/4 — NeuralCenter + CircuitEngine + NeuronPool + D_Window cleanup
- P19-W1/2/3 — Agent runtime + Agent Hub + TS archive
- P20-W1/2/3/4 — Economy/KI/Extension/Harness extraction to kairon
- P21-W1/2/3/4 — Immunity/Genesis/observability/gc-engine
- P22-W1 — Pontus DSL + scheduler
- P23-W1/2 — Hermes Console scaffold + dashboard
- P24-W1/2 — BaseMembrane zero + Nucleus替换
- P25-W2 — 文档终稿+债务关闭
- D2-CI-E2E-TEST-ENV — CI E2E baseline
- D3-EU-PRICING-TEST — eu-pricing 独立测试
- SHAREDBRAIN-FORMAL-DECISION — SharedBrain 归档决策
- ORPHANED-TASKS-STRUCTURED-REGISTRY — Orphaned tasks 结构化
- P28-W0-NORTH-STAR / P28-W0-TOOL-HEATMAP — 5+3+1 全量审计完毕
- P33-W0-FOLD — 归档旧 Phase 完成

## Archived Tasks (54 个)

> `tasks/archived/` — 54 historical tasks, 含 imported 任务。

## Blocked Tasks

当前无阻塞任务。

---
*Updated: 2026-06-11 (依据 planned/ 目录 47 个 YAML 实测重写)*
