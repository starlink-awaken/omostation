---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 12 Wave 3 执行计划：单一融合 pilot + 包生态 dry-run

> 日期: 2026-06-01 | 状态: completed
> 包名: P12-W3-SINGLE-PILOT-PKG-DRYRUN
> 入口: Wave 2 场景 MVP 可用 + P0 pilot ADR 完成
> 目标: 完成 1 个 P0 融合 pilot + 包生态 dry-run + 场景 trace

---

## G12.3.1 — 场景编排框架

**目标**: 让 Wave 2 的最小场景可重复执行并产生 trace，不扩张为完整编排平台。

| # | 任务 | 描述 | 交付物 | 验证标准 |
|---|------|------|--------|---------|
| T3.1 | 场景 trace runner | 实现 scenario.yaml → 注册表解析 → 能力绑定 → dry-run/trace 的最小链路 | `kairon.ecosystem.trace_runner` 或既有等价模块 | research-pipeline 产生可复现 trace |
| T3.2 | 绑定降级规则 | 定义能力不可用时的 fail-closed / fallback 规则 | `.omo/standards/capability-binding-policy.md` | policy 覆盖 fail-closed、fallback、audit trail |
| T3.3 | 场景执行记录 | 保存场景 trace 到交付证据目录 | `.omo/evidence/phase12/research-pipeline-trace.*` | trace 可读且引用注册表能力 ID |
| T3.4 | Phase 14 scenario backlog | 将 code-review / knowledge-search / agent-collab 等扩展场景转入 Phase 14 backlog | `phase14-deferred-ecosystem-backlog.md` update | backlog 明确 deferred reason |

**依赖**: W2 注册表工具链 + `research-pipeline` 场景

---

## G12.3.2 — 包生态管理

**目标**: 只做依赖声明和 dry-run 差异报告，不在 Phase 12 执行跨包管理器真实安装/卸载。

| # | 任务 | 描述 | 交付物 | 验证标准 |
|---|------|------|--------|---------|
| T3.5 | 依赖声明草案 | 核心项目依赖声明为 capability/package records | `registry/package-baseline.yaml` | 覆盖 kairon/agentmesh/gbrain/SharedBrain |
| T3.6 | `omo pkg` dry-run | `omo pkg sync --dry-run` 输出差异，不做真实改动 | dry-run 命令或脚本 | dry-run 报告可复现 |
| T3.7 | 包生态 Phase 14 backlog | 将 install/add/remove/list 和依赖图可视化转入 Phase 14 | `phase14-deferred-ecosystem-backlog.md` update | backlog 明确 package expansion |

**依赖**: W1 系统包扫描 (T1.8) 数据

---

## G12.3.3 — 单一 P0 融合 pilot

**目标**: 只执行 Wave 2 ADR 选中的 1 个 P0 pilot；其余 P0/P1/P2 项目进入 Phase 14。

| # | 任务 | 描述 | 交付物 | 验证标准 |
|---|------|------|--------|---------|
| T3.8 | Selected P0 pilot implementation | 执行 `phase12-p0-pilot-adr.md` 选定的 1 个 pilot | pilot implementation under approved project path | smoke test passes |
| T3.9 | Pilot rollback notes | 记录如何停用/回滚 pilot | `.omo/evidence/phase12/pilot-rollback.md` | rollback path 可读且不依赖猜测 |
| T3.10 | Deferred integration registration | GitNexus/Graphify/UltraRAG/Firecrawl/MinerU/AgentLaboratory/nuwa-skill 进入 Phase 14 backlog | `phase14-deferred-ecosystem-backlog.md` update | 每项有 deferred reason |

**依赖**: W2 注册表启用

**融合深度**: 只允许 selected pilot 达到 Level 2/3；其他项目不得在 Phase 12 执行深度吸收。

---

## G12.3.4 — 深度知识化

**目标**: 验证 Wave 2 ingestion policy，不做规模化知识图谱。

| # | 任务 | 描述 | 交付物 | 验证标准 |
|---|------|------|--------|---------|
| T3.12 | 样例检索验证 | 验证 5 条样例可按 policy 检索 | sample retrieval report | 样例可检索，来源和保留策略明确 |
| T3.13 | Knowledge graph backlog | 将批量文章知识图谱转入 Phase 14 | `phase14-deferred-ecosystem-backlog.md` update | backlog 明确 article graph scope |

**依赖**: W2 文章采集管道 (T2.7-T2.8)

---

## 交付物清单

```
kairon/
└── packages/
    └── ecosystem/                        ← 最小 trace runner 或等价模块

.omo/
├── evidence/phase12/
│   ├── research-pipeline-trace.*         ← 场景 trace
│   └── pilot-rollback.md                 ← pilot rollback notes
├── registry/
│   └── package-baseline.yaml             ← 包生态 baseline
├── standards/
│   └── capability-binding-policy.md      ← 绑定降级策略
```

---

## Exit Gate

- [x] research-pipeline trace 可复现
- [x] `omo pkg sync --dry-run` 可用，不做真实依赖改动
- [x] 1 个 P0 pilot 完成并有 rollback notes
- [x] 5 条文章样例可检索且 policy 明确
- [x] 被砍掉的 P1/P2/文章/包生态扩展全部进入 Phase 14 backlog
