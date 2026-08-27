---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-07-03
related:
  - ../decisions/0130-p74-workflow-solidification.md
  - ../decisions/0129-state-projection-plane-phase3.md
  - ../decisions/0128-state-generation-concurrency.md
  - ../../standards/p74-solidification-contract.md
  - p71-baseline-recovery-pattern.md
  - p72-follow-up-completion-pattern.md
  - p73-truth-driven-engineering-pattern.md
---

# P74 — Workflow Solidification Pattern (常态化工作流沉默治理)

> **适用范围**: 对 registry 已登记但未被实际触发、或被反复触发但缺乏专属流程的 workflow,进行系统性固化与回收。
>
> **SSOT**: `.omo/_truth/registry/agent-workflows.yaml` (`silent_workflow_policy`, `diff_checks`)
> **ADR**: [0130-p74-workflow-solidification](../decisions/0130-p74-workflow-solidification.md)
> **契约**: [p74-solidification-contract](../../standards/p74-solidification-contract.md)
> **Skill**: `.agents/skills/workflow-silence-detection/SKILL.md`
> **GaC 规则**: `CR-P74-STATE-PROJECTION-GUARD`, `CR-P74-RUNTIME-STAMP-POLICY`, `CR-P74-WORKFLOW-SILENCE`

## 1. 触发场景

任一即触发 P74 评估:

1. **沉默 workflow**:registry 登记 ≥ 1 周,无 `agent_workflow_start` 事件。
2. **错位 workflow**:实际做的事 ≥ 3 次,却走通用 `project-code-change` 而非专属 workflow。
3. **僵尸 run**:status 中 `active_runs > 0` 但 `last_closeout` 已 ≥ 24h(失忆或中断)。
4. **声明/执行鸿沟残留**(P71 §1):某文件被声明受治理(`claim_policy.required_paths`)但 `diff_checks` 无对应 gate。

## 2. 现状诊断(P74 输入)

### 2.1 矩阵盘点

对每个 workflow 取:

- `lanes` (`agent-workflows.yaml`)
- `closeout_required` 实际可执行的命令
- 最近 30 天 `agent_workflow_start` 事件计数
- 最近 30 天 `agent_workflow_closeout` 计数
- 平均 duration
- 失忆率(`status: ok` 但 24h 内无 closeout 的比例)

### 2.2 集成盘点

每个 `internal_integrations` × `external_patterns`:

- `status` (integrated / optional_adapter)
- `health` (PASS / WARN / FAIL)
- `degrade_to` 是否被声明

### 2.3 路径漂移盘点

`git log --diff-filter=A --name-only --since="<window>"` 提取新增 SSOT/工具/脚本路径,与 `claim_policy.required_paths` 做差集。

## 3. 固化分类(P74 处理)

| 类型 | 诊断特征 | 固化策略 |
|------|----------|----------|
| **A. 沉默 workflow** | 登记但无 start 事件 | 拆 3 子情况: (a1) 名称误导→改名/合并 (a2) 流程太重→拆 phase (a3) 实际无人需要→登记为 `deprecated` |
| **B. 错位 workflow** | 反复走 project-code-change | 提取专属 workflow + 专属 `diff_checks` + 强制 `allowed_lanes` |
| **C. 僵尸 run** | active 超 24h, evidence 空 | (c1) 同 actor → 续 verify/closeout (c2) 异 actor → observer-agent 介入,按 lock/ledger 决策 halt/escalate |
| **D. 鸿沟残留** | 新路径未注册 | 走 `governance-state-mutation` 流程,加进 `claim_policy.required_paths` + `diff_checks` |

## 4. P74 修复路线图(5 阶段)

详细阶段见 [ADR-0130 §3](../decisions/0130-p74-workflow-solidification.md#3-实施细节)。

阶段简述:

- **阶段 1 — 清场**:closeout 僵尸 run,`compliance.findings: []`
- **阶段 2 — 鸿沟回收**:加 `claim_policy.runtime-projection-snapshot` tier + 3 个 `diff_checks`
- **阶段 3 — 错位路由**:`agent-workflow suggest --from-diff` advisory
- **阶段 4 — 沉默分层**:A1(检查层)/ A2(运行层)区分
- **阶段 5 — 自我演化**:`p74_solidification_report` 内嵌 compliance

## 5. 防复发机制(对应 ADR-0130 §4.2)

| 风险 | 缓解 |
|------|------|
| omo state sync 改坏派生 | `--include-p74` flag 默认 off |
| suggest 误报 | advisory only,不强制 |
| governance-checks 规则过期 | `gac-validate` 自动验证 |
| P74 pattern 文档过期 | 全部指针到 SSOT;`last-reviewed` 字段强制刷新 |
| 命名空间漂移 | 走 `omo-` 前缀(归 OMO 域);CR-META-BIN-NAMING 拦截 |

## 6. 与 P71/P72/P73 关系

| Pattern | 性质 | 与 P74 关系 |
|---------|------|------------|
| P71 baseline-recovery | 一次性鸿沟修复(5 阶段) | P74 是 P71 的常态化扩展 |
| P72 follow-up-completion | 阶段路线图执行守门 | P74 借鉴执行守门 |
| P73 truth-driven | SSOT 驱动工程 | P74 用 SSOT 但贡献 SSOT |
| **P74** | **常态化机制** | **把 P71/P72 的发现沉淀到 workflow 层级** |

## 7. 与 ADR 链关系

- ADR-0106:GaC 总决策
- ADR-0115:bin 命名空间(被 P74 引用)
- ADR-0128:状态生成并发(P74 输入)
- ADR-0129:运行时投影面(P74 输入)
- **ADR-0130(本 pattern 对应)**:常态化工作流沉默治理

## 8. 长期维护

### 8.1 主动触发

P74 报告通过 omo state sync 派生进 `.omo/state/runtime/health.yaml`(observability 阶段)。
当前阶段(PR #X)手动触发:`uv run --with pyyaml python bin/agent-workflow.py compliance`。

### 8.2 排错路径

参见 [p74-solidification-contract §3](../../standards/p74-solidification-contract.md#3-decision-tree操作员视角)。

### 8.3 治理信号

`p74_solidification.warn_count` 持续增长 → workflow registry 漂移,需要审查。

## 9. 立即执行项(P74 PR 范围)

按本模式执行:

1. 阶段 1 — 关闭 active run(已有 active run 时)
2. 阶段 2 — 在 `agent-workflows.yaml` 注册新路径
3. 阶段 3 — 写 suggest 命令
4. 阶段 4 — 加 `silent_workflow_policy`
5. 阶段 5 — 加 `p74_solidification_report` 到 compliance

PR 验证标准见 [ADR-0130 §5](../decisions/0130-p74-workflow-solidification.md#5-验证标准)。

阶段 6+ (可选,observability 阶段):接 omo state sync、bootstrap 摘要、cockpit compass 视图。