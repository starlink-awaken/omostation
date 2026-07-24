## 当前运行时状态
> 运行时状态不要在此页硬编码。
> 当前 phase / health / code_freeze / milestones 一律以 [state/system.yaml](state/system.yaml)、
> [goals/current.yaml](goals/current.yaml) 与对应 delivery/audit 证据为准。

---

# `.omo/` — OMO 治理状态面

> `.omo/` 不是治理执行内核，而是治理状态承载面。
> 权威边界定义见 [standards/omo-governance-surfaces.md](standards/omo-governance-surfaces.md)。

## 治理联动

`.omo/` 只是状态承载面，不是完整治理系统。

当前治理以三层联动为准：

| 层 | 位置 | 说明 |
|---|---|---|
| 状态面 | `.omo/` | 真相、控制、知识、交付、任务与证据 |
| 内核面 | `projects/omo/` | schema、governance、sync、overlay、promotion |
| 入口面 | `projects/c2g/` | Pitch / OpenSpec / Fast-Track 到 Planned Tasks |

权威标准与注册表：

- [standards/omo-governance-surfaces.md](standards/omo-governance-surfaces.md)
- [_truth/registry/omo-governance-surfaces.yaml](_truth/registry/omo-governance-surfaces.yaml)
- [_truth/registry/mutation-surfaces.yaml](_truth/registry/mutation-surfaces.yaml)
- [_truth/registry/internal-write-profiles.yaml](_truth/registry/internal-write-profiles.yaml)
- [_truth/registry/task-policies.yaml](_truth/registry/task-policies.yaml)
- [_truth/registry/direct-io-baseline.yaml](_truth/registry/direct-io-baseline.yaml)

### 持久化写入规则

- `.omo/` 是状态承载面，不是自由写盘区。
- 人类/桥接写入入口必须走 `projects/omo` broker 或 `projects/c2g` ingress。
- worker/internal 运行时写路径必须登记，不得用 ad-hoc 脚本直接写 `.omo/`。
- `direct-io-baseline.yaml` 当前应保持空基线；新增 entry 代表出现新的直写违规。
- 机器门禁入口:
  - `omo lint direct-omo-io`
  - `omo lint mutation-surfaces`
  - `omo lint internal-write-profiles`

---

## 当前状态入口

| 指标 | 权威读源 |
|------|----------|
| Phase / Wave / Health | [state/system.yaml](state/system.yaml) |
| Goals / code freeze / milestone | [goals/current.yaml](goals/current.yaml) |
| Active / Planned / Done Tasks | [tasks/](tasks/) |
| 战略计划 | [plans/](plans/) |
| 审计证据 | [_delivery/](_delivery/) |
| 复盘与说明 | [_knowledge/](_knowledge/) |

---

## 状态面导航

| 平面 | 入口 | 回答的问题 |
|------|------|-----------|
| **控制面** | [_control/INDEX.md](_control/INDEX.md) | 我现在在哪？下一步做什么？ |
| **事实面** | [_truth/INDEX.md](_truth/INDEX.md) | 什么是真的？权威信息在哪？ |
| **知识面** | [_knowledge/INDEX.md](_knowledge/INDEX.md) | 我们知道了什么？ |
| **交付面** | [_delivery/INDEX.md](_delivery/INDEX.md) | 我们交付了什么？ |

---

## 快速入口

| 目标 | 位置 |
|------|------|
| 当前任务 | [tasks/active/](tasks/active/) |
| 当前目标 | [goals/current.yaml](goals/current.yaml) |
| 系统状态 | [state/system.yaml](state/system.yaml) |
| 债务仪表盘 | [debt/dashboard/current.yaml](debt/dashboard/current.yaml) |
| 质量标准 | [standards/](standards/) |
| 计划注册表 | [_knowledge/design/plans/README.md](_knowledge/design/plans/README.md) |
| 历史复盘 | [_knowledge/summaries/README.md](_knowledge/summaries/README.md) |
| 历史任务 | [tasks/done/](tasks/done/) |
| 架构基线 | [_knowledge/design/system-design-baseline.md](_knowledge/design/system-design-baseline.md) |
| 治理历史 (JSONL) | [_knowledge/governance-history.jsonl](_knowledge/governance-history.jsonl) |
| AppendOnlyLog 模式 | [_knowledge/management/append-only-log-pattern-2026-06-09.md](_knowledge/management/append-only-log-pattern-2026-06-09.md) |

---

## 核心规范与 SSOT

- [standards/omo-governance-surfaces.md](standards/omo-governance-surfaces.md) — `.omo` / `projects/omo` / `projects/c2g` 三层治理契约
- [_truth/registry/omo-governance-surfaces.yaml](_truth/registry/omo-governance-surfaces.yaml) — 机器可读治理面注册表
- [_truth/x1-governance-policies.yaml](_truth/x1-governance-policies.yaml) — X1 边界 / 写入 / 审计策略
- [_truth/x2-freshness-rules.yaml](_truth/x2-freshness-rules.yaml) — X2 保鲜规则
- [_truth/x3-value-stack.yaml](_truth/x3-value-stack.yaml) — X3 价值与成本归因
- [_truth/x4-consistency-rules.yaml](_truth/x4-consistency-rules.yaml) — X4 一致性规则

- [_archive/legacy-root-docs/DOC-ARCH.md](_archive/legacy-root-docs/DOC-ARCH.md) — 四平面文档架构定义
- [AGENT.md](_knowledge/usage/AGENT.md) — Agent 行为规范
- [DOC-LIFECYCLE.md](DOC-LIFECYCLE.md) — `.omo/` 文档 4 类分类 + frontmatter schema + 引用规则 (P45)

---

## 文档生命周期入口 (P45)

> 4 类文档分类 + 机器校验。详见 [DOC-LIFECYCLE.md](DOC-LIFECYCLE.md)

| 类别 | 路径模式 | 例子 | 机器校验 |
|------|---------|------|---------|
| **SSOT** (机器) | `.omo/_truth/*.yaml` | x1-x4, mutation-surfaces, mof-version | `omo lint doc-lifecycle` |
| **CONTRACT** (人+工具) | `.omo/standards/*.md` | omo-governance-surfaces, task-yaml-rules | `omo lint doc-lifecycle` |
| **PATTERN** (模板) | `.omo/_knowledge/patterns/*.md` | p43/p44 closed-loop | `omo lint doc-lifecycle` |
| **ARCHIVE** (历史) | `.omo/_archive/`, `_knowledge/audits/`, `_knowledge/management/` | 31 phase closeout, 142 decisions | (无 lint) |

**frontmatter 模板**:
```yaml
---
status: active | deprecated | archived | experimental
lifecycle: ssot | contract | pattern | history
owner: <domain>
last-reviewed: YYYY-MM-DD
---
```

**X2 巡检**: `X2-FRESH-DOC-LIFECYCLE` (7 天) — frontmatter 覆盖率 + 死文档占比 + 矛盾路径

---

## 治理历史

每次 governance audit 跑完会 append 一条到 `_knowledge/governance-history.jsonl`。

查看最近 30 天分数：

```bash
omo governance
```

记录格式：`{date, timestamp, total_score, grade, checks[], watchlist_count}`

---

## 标准规范全索引 (standards/)

### 流程与协议

- [standards/adr-process.md](standards/adr-process.md) — ADR 生命周期流程
- [standards/agent-cli-worker-collaboration.md](standards/agent-cli-worker-collaboration.md) — Agent/CLI/Worker 协作协议
- [standards/agent-mutation-protocol.md](standards/agent-mutation-protocol.md) — Agent 变异协议
- [standards/agent-registry-heartbeat.md](standards/agent-registry-heartbeat.md) — Agent 注册心跳
- [standards/agent-workflow-contract.md](standards/agent-workflow-contract.md) — Agent 工作流契约
- [standards/article-ingestion-policy.md](standards/article-ingestion-policy.md) — 文章摄入策略
- [standards/auto-generated-artifacts.md](standards/auto-generated-artifacts.md) — 自动产物规范
- [standards/bin-tool-naming.md](standards/bin-tool-naming.md) — bin 工具命名规范
- [standards/bos-uri-domain-standard.md](standards/bos-uri-domain-standard.md) — BOS URI 域标准
- [standards/debt-gate-level-enum.md](standards/debt-gate-level-enum.md) — 债务门禁级别枚举
- [standards/doc-presentation-pattern.md](standards/doc-presentation-pattern.md) — 文档呈现模式

### 能力与约束

- [standards/capabilities.schema.yaml](standards/capabilities.schema.yaml) — 能力 schema
- [standards/capability-binding-policy.md](standards/capability-binding-policy.md) — 能力绑定策略
- [standards/capability-metamodel.md](standards/capability-metamodel.md) — 能力元模型
- [standards/divergence-triage.yaml](standards/divergence-triage.yaml) — 分歧分诊规则
- [standards/doc-ssot-contract.md](standards/doc-ssot-contract.md) — 文档 SSOT 契约
- [standards/health-metrics-semantics.md](standards/health-metrics-semantics.md) — 健康指标语义
- [standards/interface_contract.md](standards/interface_contract.md) — 接口契约
- [standards/kos-baseline-drift-monitor.md](standards/kos-baseline-drift-monitor.md) — KOS 基线漂移监控

### MCP / MOF / OPC

- [standards/mcp-tool-and-transport-standard.md](standards/mcp-tool-and-transport-standard.md) — MCP 工具与传输标准
- [standards/mof-agent-constraints.yaml](standards/mof-agent-constraints.yaml) — MOF Agent 约束
- [standards/mutation-proposal-envelope.md](standards/mutation-proposal-envelope.md) — 变异提案信封
- [standards/opc-review-template.md](standards/opc-review-template.md) — OPC 评审模板
- [standards/omo-submodule-split-validation.md](standards/omo-submodule-split-validation.md) — 子模块拆分验证规范
- [standards/operation-levels.md](standards/operation-levels.md) — 操作级别定义

### P74 / P76 / 阶段

- [standards/p74-solidification-contract.md](standards/p74-solidification-contract.md) — P74 常态化契约
- [standards/p76-principles.md](standards/p76-principles.md) — P76 原则
- [standards/phase2-full-execution-go-no-go.md](standards/phase2-full-execution-go-no-go.md) — Phase2 执行 Go/No-Go
- [standards/planning-blueprint-delivery-test-standard.md](standards/planning-blueprint-delivery-test-standard.md) — 规划-交付-测试标准

### Schema / SSOT / 模板

- [standards/scenario.schema.yaml](standards/scenario.schema.yaml) — 场景 schema
- [standards/ssot-7-domain-schema.md](standards/ssot-7-domain-schema.md) — SSOT 7 域 schema
- [standards/ssot-guardian.md](standards/ssot-guardian.md) — SSOT 守护者
- [standards/submodule-inclusion-policy.md](standards/submodule-inclusion-policy.md) — 子模块纳入策略

### 任务 / X1-X4

- [standards/task-gate-model.md](standards/task-gate-model.md) — 任务门禁模型
- [standards/task-yaml-rules.md](standards/task-yaml-rules.md) — 任务 YAML 规则
- [standards/x1-swarm-trust-protocol.md](standards/x1-swarm-trust-protocol.md) — X1 Swarm 信任协议
- [standards/x2-budget-integrity-standard.md](standards/x2-budget-integrity-standard.md) — X2 预算完整性标准
- [standards/x2-rule-template-standard.md](standards/x2-rule-template-standard.md) — X2 规则模板标准
- [standards/x3-value-stack-standard.md](standards/x3-value-stack-standard.md) — X3 价值栈标准
- [standards/x4-hitl-mutation-standard.md](standards/x4-hitl-mutation-standard.md) — X4 HITL 变异标准
- [standards/PITCH-TEMPLATE-C2G.md](standards/PITCH-TEMPLATE-C2G.md) — C2G 提案模板
- [standards/README.md](standards/README.md) — 规范索引

---

## goals / state / tasks

- [goals/README.md](goals/README.md) — 目标索引
- [state/README.md](state/README.md) — 状态索引
- [state/health.yaml](state/health.yaml) — 健康度指标
- [state/provider-plane.yaml](state/provider-plane.yaml) — 供应面状态
- [state/system_health.yaml](state/system_health.yaml) — 系统健康快照
- [tasks/README.md](tasks/README.md) — 任务索引

---

*维护: 2026-07-14 · 此页只保留导航与指针，不再复制运行时事实*
