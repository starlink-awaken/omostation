# GaC Rules & Agent Workflows Exploration Report

> Generated: 2026-08-01 by gac-workflow-explorer agent
> Purpose: 为 slimming 计划提供数据结构、数量、分布全景

---

## 1. GaC Rules — governance-checks.yaml

### 1.1 文件结构

路径: `/Users/xiamingxing/Workspace/.omo/_truth/registry/governance-checks.yaml` (2728 行)

文件是 **双 YAML 文档** (`---` 分隔):
- Doc 0: 元数据 frontmatter (status/lifecycle/owner/last-reviewed)
- Doc 1: 主体 (version/description/checkers/execution/alerting/**gac**)

核心 GaC 段在 `gac.rules[]` 下。

### 1.2 规则 Schema (必填字段)

```yaml
required: [id, dimension, layer, check_type, executor, lifecycle, version, created_at]
# source_type=nindexed 时额外必填: source_ref
```

枚举:
- `dimension`: X1 | X2 | X3 | X4
- `layer`: M0 | L0 | L1 | L2 | L3 | L4 | I0 | X | meta
- `check_type`: 36 种 (ssot_pointer, mof_stage_gate, bos_resolve, drift_audit, legacy_index, ...)
- `lifecycle`: draft | active | deprecated | removed
- `executor`: hook_pre_edit | hook_post | ci_gate | omo_audit | mcp_tool | mof_validate | mof_audit | evidence_smoke | radar_cron | gc_cron | gac_local_gate | foundry_cron

### 1.3 数量统计

| 指标 | 值 |
|------|-----|
| **GaC 规则总数** | **191** |
| active | 185 |
| draft | 6 |
| deprecated | **0** (没有已废弃规则!) |
| removed | 0 |
| native (原生) | 87 |
| indexed (遗留索引) | 104 |

**P79 冻结声明**: `freeze.max_rules=173` (2026-07-08 生效), 但实际规则数 **191** — 已超冻结线 18 条! 豁免流程是 "ADR + governance-team approval"。

### 1.4 Red vs Gray 分布

判定逻辑: executor 含 `ci_gate` 或 `hook_pre_edit` → **Red (阻断 CI)**, 否则 → **Gray (仅告警)**。

| 类型 | 数量 | 占比 |
|------|------|------|
| **Red (阻断)** | **177** | 92.7% |
| **Gray (warn only)** | **14** | 7.3% |

### 1.5 Check Type 分布 (Top 15)

| check_type | 数量 | 说明 |
|------------|------|------|
| legacy_index | 102 | 遗留索引 (占 53%!) |
| value_roi | 16 | X3 价值栈 |
| drift_audit | 14 | 漂移审计 |
| consistency_drift | 12 | 一致性漂移 |
| audit_chain | 9 | 审计链 |
| ssot_pointer | 7 | SSOT 指针 |
| registry_integrity | 6 | 注册表完整性 |
| freshness | 3 | 新鲜度 |
| ssot_lint | 3 | SSOT lint |
| bos_resolve | 2 | BOS 解析 |
| hygiene_case | 2 | 大小写 hygiene |
| schema_integrity | 2 | schema 完整性 |
| god_module | 2 | God Module |
| doc_lifecycle | 2 | 文档生命周期 |
| mof_stage_gate | 1 | M0 Stage/Gate |

### 1.6 Dimension 分布

| 维度 | 规则数 |
|------|--------|
| X4 一致性 | 81 |
| X1 审计链 | 47 |
| X2 抗熵 | 31 |
| X3 价值栈 | 32 |

### 1.7 Draft 规则 (6 条)

- CR-CROSS-REPO: 跨仓一致性规则族
- CR-CROSS-REPO-REGISTRY-CONSISTENT: 跨仓注册表一致性
- CR-PR-DESCRIPTION-NON-EMPTY: PR 描述非空
- CR-PRINCIPLE-ENFORCEMENT: 原则执行化
- CR-RUFF-SCOPE-STABLE: Ruff Scope 稳定
- CR-WORKTREE-CLEAN-BEFORE-PR: Worktree 清理

### 1.8 规则的 Deprecation 机制

`lifecycle` 字段驱动, 状态机: `draft → active → deprecated → removed`

- `draft_to_active_days: 7` (7 天后 radar 验证执行 → 转 active)
- drift 自检: `alert_on: [missing_executor, ghost_rule, version_mismatch]`
- **现状**: `deprecated` 枚举已定义但 **0 条规则使用** — deprecation 机制从未被激活
- `gc_cron` executor 已声明但 **未实现** (阶段 2 待办)

### 1.9 前 5 条规则 / 最后 5 条规则

**前 5 条** (均为 active + native + ci_gate/hook_pre_edit):
1. CR-X4-HEALTH-SSOT — 健康分 SSOT (X4, L2)
2. CR-M0-STAGE-GATE — M0 7 阶段 Stage/Gate (X4, M0)
3. CR-L0-BOS-RESOLVE — BOS 声明/执行一致 (X1, L0)
4. CR-L2-TASK-DELIVERABLE — 任务 deliverable 必填 (X4, L2)
5. CR-X2-GAC-DRIFT — GaC drift 自检 (X2, meta)

**最后 5 条** (均为 indexed + legacy_index):
1. CR-OMLX-MESH-GATE-01 — L0 遗留治理闭环约束
2. CR-KOS-CONSENSUS-RAG-01 — KOS 共识 RAG
3. CR-C2G-INGRESS-PRECHECK-01 — C2G 入口预检
4. CR-KOS-ONTOLOGY-DRIFT-01 — KOS 本体漂移
(最后一条在 2710 行结束)

---

## 2. Agent Workflows — agent-workflows.yaml

### 2.1 文件结构

路径: `/Users/xiamingxing/Workspace/.omo/_truth/registry/agent-workflows.yaml` (1364 行)

核心段:
- `runner`: 入口/运行态/ledger 配置
- `silent_workflow_policy`: P74 沉默治理策略
- `requirement_iteration_policy`: ADR-0203 强制 workflow
- `claim_policy`: 路径分级 (core-governance-required / runtime-projection-snapshot / agent-entrypoint-advisory)
- `workflows[]`: 工作流定义
- `agent_profiles[]`: 13 个 agent profile
- `external_patterns`: 外部适配器 (superpowers/bmad/openspec/gstack/beads)

### 2.2 全部 Workflow ID + run_frequency

| workflow ID | run_frequency | 说明 |
|-------------|---------------|------|
| project-doc-change | on_demand | 文档变更 |
| project-code-change | on_demand | 代码变更 |
| governance-state-mutation | on_demand | 治理状态变更 |
| c2g-spec-ingress | periodic | 策略入口 |
| mof-model-change | on_demand | MOF 模型变更 |
| mof-state-bridge-audit | periodic | MOF 状态桥审计 |
| external-adapter-sync | periodic | 外部适配器同步 |
| submodule-pointer-close | on_demand | submodule 指针 |
| handoff-resume | on_demand | 接续恢复 |
| observer-audit | continuous | 只读监督 |
| state-sync | continuous | 状态同步 |
| governance-audit | periodic | 治理审计 |

**分布**: on_demand=7, periodic=4, continuous=2

### 2.3 最近运行数据

- 运行记录数: **173** (`.omo/_delivery/agent-workflows/runs/`)
- 事件总数: **569** (`.omo/_delivery/agent-workflows/events.jsonl`)

事件类型分布:
| 事件 | 数量 |
|------|------|
| agent_workflow_close | 182 |
| agent_workflow_start | 172 |
| agent_workflow_claim | 84 |
| agent_workflow_verify | 81 |
| agent_workflow_closeout | 50 |

**观察**: start(172) vs close(182) 差 10 个 — 有无关闭的孤儿 run。closeout(50) 远低于 start(172) — 仅 ~29% 完成完整生命周期。

### 2.4 P74 沉默策略

- `warn_after_days: 30`
- `excluded_workflows` 字段已删除 (ADR-0211 §D1)
- 无 `run_frequency` 差异化阈值 (on_demand 30d / periodic 7d / continuous 1d 的逻辑在注释中提及但未实现)

### 2.5 Agent Profiles (13 个)

docs-agent, engineering-agent, qa-agent, governance-agent, state-sync-agent, mof-agent, c2g-agent, strategy-agent, adapter-agent, release-agent, observer-agent, any-agent + 外部 superpowers 集成。

---

## 3. GAC Local Gate — gac-local-gate.py

路径: `/Users/xiamingxing/Workspace/bin/gac/gac-local-gate.py` (513 行)

### 3.1 执行机制

- 读取 `sgf-policy.yaml` (ecos 子模块), 缺失时 fallback 到硬编码 `DEFAULT_POLICY`
- `DEFAULT_POLICY.gates[]` 包含 **53 个 gate**
- 每个 gate 格式: `{id, command, ci_skip?, ci_only?, agent_workflow_only?, broken?}`

### 3.2 跳过逻辑

| 条件 | 行为 |
|------|------|
| `ci_only=True` + 非 strict | pre-commit 跳过, CI 跑 |
| `ci_skip=True` + CI 环境 | CI 跳过 (本地运维 check) |
| `agent_workflow_only=True` + staged 不涉及 | 跳过 |
| `broken=True` + 非 strict | 跳过 (已知不可用) |
| `SOFT_CHECKS` 集合 | 不翻转 gate (仅 WARN) |

**SOFT_CHECKS**: `governance-semantic-gate`, `brief-protect`

### 3.3 能否 skip deprecated rules?

**不能** — 当前 gate 没有 lifecycle/deprecated 概念。唯一的"跳过"机制是 `broken: True`。

要支持 deprecated skip, 需要:
1. 在 gate 条目中加 `lifecycle` 字段
2. 在 `gate_checks()` 中加 `if g.get('lifecycle') == 'deprecated': continue`

---

## 4. Governance Evolution Roadmap

路径: `/Users/xiamingxing/Workspace/.omo/_truth/registry/governance-evolution-roadmap.yaml` (354 行)

### 4.1 8 大 Initiative (全部 active)

| ID | 进度 | 层 |
|----|------|-----|
| worktree-release-convergence | 10% | X4 |
| cockpit-governance-status-plane | 20% | L3 |
| claim-policy-tiering | 30% | X1 |
| bos-governance-evolution-routes | 40% | I0 |
| capability-traceability | 50% | X4 |
| governance-operating-rhythm | 80% | L2-L0 |
| golden-path-e2e | 70% | X1-X4 |
| entrypoint-convergence | 80% | L3-I0-X |

### 4.2 规则生命周期描述

Roadmap 本身不直接描述规则生命周期。生命周期定义在 `governance-checks.yaml` 的 `gac.lifecycle` 段:
- `draft_to_active_days: 7`
- 阶段 2 实现状态机 + gc 原语清理 (未实现)
- `freeze.max_rules=173` (P79 Phase 5)

### 4.3 运营节奏

- **daily**: agent-workflow status, governance-evolution status+packages
- **pre_release**: gac-local-gate, agent-workflow compliance, governance-evolution validate
- **weekly**: mof-state-bridge, mof-drift

---

## 5. 触发历史追踪

### 5.1 现状: **无 per-rule 触发追踪**

| 机制 | 追踪内容 | 路径 |
|------|---------|------|
| events.jsonl | workflow 生命周期事件 (start/claim/verify/close/closeout) | `.omo/_delivery/agent-workflows/events.jsonl` (569 条) |
| governance-alerts.yaml | 告警规则定义 (channel/severity/condition), 无历史 | `.omo/_truth/registry/governance-alerts.yaml` |
| drift 自检 | missing_executor/ghost_rule/version_mismatch | governance-checks.yaml::gac.drift |
| optimization-design.md | 设计文档中有 `CREATE TABLE alert_history` SQLite schema | `.omo/_knowledge/governance/optimization-design.md` (未实现) |

**结论**: GaC 规则没有 "上次触发时间"、"触发次数"、"最近 N 次结果" 等追踪。无法判断哪些规则从未触发、哪些天天误报。

### 5.2 审计日志 (间接相关)

`.omo/_knowledge/audits/` 目录下有历史审计文件 (2026-06-13 ~ 2026-07-24), 但这些都是专项审计报告, 非自动化触发追踪。

---

## 6. Slimming 建议摘要

### 规则瘦身机会

1. **legacy_index 102 条** (53%) — 这些是遗留索引, source_type=indexed, 指向 `L0-constraints.yaml`. 如果原策略 SSOT 仍有效, 可压缩为 1 条 "legacy-index-drift" 规则
2. **177 条 Red 规则** — 92.7% 阻断率过高, 大部分 legacy_index 规则实际是 advisory, 可降为 Gray
3. **6 条 draft 规则** — 长期停留 draft, 应决定 active 或删除
4. **P79 冻结已破** — 173→191, 需治理
5. **deprecated 状态未使用** — deprecation 机制从未激活, 需要启用

### Workflow 瘦身机会

1. **closeout 率仅 29%** — 71% 的 run 未正确 closeout, 需调查原因
2. **on_demand=7** — 大部分 workflow 是按需的, 可合并相似 workflow (如 mof-model-change + mof-state-bridge-audit)
3. **periodic=4** — c2g-spec-ingress / external-adapter-sync 使用频率可能极低

### 触发追踪建设

1. 需要在 GaC gate 执行时记录 per-rule 触发 (rule_id, timestamp, result, duration)
2. `alert_history` 表 (optimization-design.md 已设计) 应实现
3. 基于触发数据驱动 deprecation 决策 (90 天未触发 → 候选 deprecated)
