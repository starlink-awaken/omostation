# Agent 必读手册 — `.omo/` 治理知识库

> 你（AI Agent）在 `.omo/` 治理知识库中扮演协作者角色。本文档是你每次会话启动时的必读指南。
>
> 体系架构详见 [DOC-ARCH.md](DOC-ARCH.md) · 全局导航详见 [INDEX.md](INDEX.md)

---

## 一、会话启动流程

每次新会话开始时，按以下顺序阅读：

| 步骤 | 读什么 | 为什么 |
|------|--------|--------|
| 1 | [INDEX.md](INDEX.md) | 了解四平面入口和目录结构 |
| 2 | [DOC-ARCH.md](DOC-ARCH.md) | 理解 SSOT 本体建模思想和文件规范 |
| 3 | [state/system.yaml](state/system.yaml) | 查看当前系统状态（Phase、健康分、任务统计） |
| 4 | [goals/current.yaml](goals/current.yaml) | 查看当前 Phase 目标和进度 |
| 5 | [tasks/README.md](tasks/README.md) | 了解任务 schema 和状态流转 |
| 6 | [tasks/active/](tasks/active/) | 查看可认领的活跃任务 |

> **启动检查**：读完上面 6 步后，你应该知道：系统在哪一阶段、状态是否健康、还有哪些任务可做。

---

## 二、四平面导航速查

### 我在哪？→ 控制面 `_control/`

| 你想找 | 去哪儿 |
|--------|--------|
| 当前 Phase 和目标 | [goals/current.yaml](goals/current.yaml) |
| 系统运行状态 | [state/system.yaml](state/system.yaml) |
| Provider 状态 | [state/provider-plane.yaml](state/provider-plane.yaml) |
| 一致性检查结果 | [CONSISTENCY-CHECK.md](CONSISTENCY-CHECK.md) |
| 战略蓝图 | [MASTER-BLUEPRINT.md](MASTER-BLUEPRINT.md) |

### 什么是真的？→ 事实面 `_truth/`

| 你想找 | 去哪儿 |
|--------|--------|
| 可认领的任务 | [tasks/active/](tasks/active/) |
| 任务 schema 规范 | [tasks/README.md](tasks/README.md) |
| 治理标准 | [standards/README.md](standards/README.md) |
| 操作分级（L0-L3） | [operation-levels.md](standards/operation-levels.md) |
| Worker 注册表 | [workers/registry.yaml](workers/registry.yaml) |
| 项目注册表 | [PROJECTS.yaml](PROJECTS.yaml) |

### 我们知道了什么？→ 知识面 `_knowledge/`

| 你想找 | 去哪儿 |
|--------|--------|
| 设计文档/计划 | [_knowledge/design/INDEX.md](_knowledge/design/INDEX.md) |
| 复盘总结 | [_knowledge/process/INDEX.md](_knowledge/process/INDEX.md) |
| 审计报告 | [_knowledge/management/INDEX.md](_knowledge/management/INDEX.md) |
| 使用指南 | [_knowledge/usage/INDEX.md](_knowledge/usage/INDEX.md) |
| 参考/经验/架构图 | [_knowledge/reference/INDEX.md](_knowledge/reference/INDEX.md) |

### 我们交付了什么？→ 交付面 `_delivery/`

| 你想找 | 去哪儿 |
|--------|--------|
| Worker 运行记录 | [workers/runs/](workers/runs/) |
| 测试记录 | [tests/](tests/) |
| 交付证据 | [evidence/](evidence/) |
| 会话续接 | [../runtime/run-continuation/](../runtime/run-continuation/) |

---

## 三、SSOT 读写规范

### 读规则

| 数据类型 | 唯一读源 | 禁止行为 |
|---------|---------|---------|
| 任务数据 | `tasks/` 下的 YAML 文件 | 从知识面文档中读取任务信息（可能过时） |
| 标准定义 | `standards/` 下的标准文件 | 从计划文档中读取标准内容 |
| 系统状态 | `state/system.yaml` | 从旧快照（如 HEALTH_DASHBOARD.md）中取状态值 |
| 目标定义 | `goals/current.yaml` | 从复盘文档中读取目标信息 |

### 写规则

| 操作 | 写入位置 | 前提条件 |
|------|---------|---------|
| 创建新任务 | `tasks/active/` | 必须符合 YAML schema（14 必填字段） |
| 完成任务 | `tasks/done/` | 必须提供 evidence + 更新 state |
| 更新状态 | `state/system.yaml` | 通过 `scripts/sync_omo_state.py` 自动完成 |
| 更新目标 | `goals/current.yaml` | ⚠️ 仅人类可修改，Agent 只能读取 |
| 记录交付 | `workers/runs/` 或 `evidence/` | 必须包含可重现的执行上下文 |

### SSOT 铁律

> **同一事实不在多处写。知识面文档引用事实面数据时，必须使用相对路径指针，不得复制内容。**

错误示范：
```markdown
<!-- ❌ 错误：复制了任务状态 -->
任务 M2.5 状态: completed
```

正确示范：
```markdown
<!-- ✅ 正确：使用指针引用 -->
任务 M2.5 状态: 参见 `tasks/done/M2.5-*.yaml`（实际文件以 `tasks/done/` 目录为准）
```

---

## 四、任务执行流程

### 从认领到完成

```
1. 查看 active/ 任务列表
    → 检查 risk_level + allowed_operation_level
    → 确认 human_approval_required

2. 阅读 source_docs
    → 理解任务上下文
    → 检查 depends_on 是否已满足

3. 执行任务
    → 准备 evidence（输出文件/测试结果/截图）
    → 记录执行过程

4. 更新任务状态
    → in_progress → review → done
    → 填写 evidence_required 字段
    → 更新 state/system.yaml（通过 sync 脚本）

5. 记录交付
    → 交付证据写入 _delivery/ 对应位置
    → 运行记录写入 workers/runs/ 或 evidence/
```

### 任务 YAML 必填字段

```yaml
id: M2.5-xxx              # 唯一标识
phase: 2                  # 所属 Phase
milestone: M2.5           # 里程碑
priority: high            # 优先级
title: "任务标题"          # 简明描述
status: pending           # candidate|pending|in_progress|review|done|blocked|failed
assigned_to: agent-name   # 认领者
source_docs: []           # 参考文档列表
depends_on: []            # 依赖任务列表
risk_level: L1            # L0|L1|L2|L3（L2/L3 需 approval_ref）
allowed_operation_level: L1  # L0|L1|L2|L3
human_approval_required: false  # 布尔值
evidence_required: []     # 预期证据清单
test_plan: []             # 测试计划
```

### L2/L3 高风险任务

对于 `risk_level: L2` 或 `risk_level: L3` 的任务：
- 必须获取 `human_approval_required: true` 的人类审批
- 必须填写 `approval_ref` 记录审批证据
- 执行完成后必须填写 `review_ref` 记录审查证据

---

## 五、文档创建规范

当你需要创建新文档时，按以下规则选择放置位置：

| 你要写什么 | 放在哪 | 前置条件 |
|-----------|--------|---------|
| 设计方案、规格书 | `.omo/_knowledge/design/` | 先创建对应任务 |
| 复盘总结 | `.omo/_knowledge/process/` | 交付完成后方可复盘 |
| 审计报告 | `.omo/_knowledge/management/` | 审计任务完成后 |
| 使用指南、操作手册 | `.omo/_knowledge/usage/` | 功能稳定后 |
| 参考文档、术语表 | `.omo/_knowledge/reference/` | 知识沉淀后 |
| Worker 运行记录 | `.omo/workers/runs/` | 调度执行后自动记录 |
| 交付证据 | `.omo/evidence/` | 任务完成后 |
| 测试文件 | `.omo/tests/` | 对应功能开发中 |

**命名规范**：使用 kebab-case，如 `llm-convergence-requirements.md`

---

## 六、一致性检查清单

在完成任何工作之前，检查以下项目：

- [ ] `state/system.yaml.phase` 与 `goals/current.yaml.phase` 对齐
- [ ] 完成的任务已从 `tasks/active/` 移到 `tasks/done/`
- [ ] 任务状态流转正确（`pending → in_progress → review → done`）
- [ ] 高风险任务（L2/L3）有 `approval_ref` 和 `review_ref`
- [ ] 交付证据已记录在 `_delivery/` 对应位置
- [ ] 知识面文档标注了 `freshness` 日期
- [ ] 引用了事实面 SSOT 数据时使用指针而非副本

### Canonical `.omo` verification command

Use this command when you need proof that the Workspace `.omo` governance surface is green:

- `bash bin/verify-omo.sh`

Equivalent local wrapper:

- `make governance-verify`

This canonical chain covers:

1. `python3 scripts/sync_omo_state.py --omo-dir .omo`
2. `python3 scripts/omo_worker.py task validate --all-active`
3. `python3 -m pytest .omo/tests -q`

The following are partial checks only and must not be mistaken for full `.omo` verification:

- `make governance-sync`
- `make governance-validate`
- `make governance-index-check`

### Debt governance refresh

Use this when you need to refresh the first-class debt ledger surfaces before reading debt state:

1. `python3 scripts/omo_debt.py refresh --omo-dir .omo --now 2026-06-10T00:00:00Z`
2. `python3 scripts/omo_debt.py dispatch --omo-dir .omo --now 2026-06-10T00:00:00Z`
3. `python3 scripts/omo_debt.py campaign --omo-dir .omo`
4. `python3 scripts/omo_debt.py report --omo-dir .omo`
5. `python3 scripts/sync_omo_state.py --omo-dir .omo`
6. `bash bin/verify-omo.sh`

- `.omo/debt/registry.yaml` now publishes `campaign_ref` and `reporting_ref` as the canonical debt entrypoints for run-level coordination and compact run progress
- `state/system.yaml` promotes `debt_reporting_ref` as the high-level debt progress pointer; campaign remains registry-only because it is still operator-detail
- Canonical refresh -> dispatch -> campaign -> report -> sync -> verify flow: `refresh` -> `dispatch` -> `campaign` -> `report` -> `sync_omo_state.py` -> `bash bin/verify-omo.sh`
- Missing generated files behind `campaign_ref` or `reporting_ref` are debt-control-plane drift, not silent success

Interpretation rules:

- `.omo/debt/registry.yaml` is the canonical debt index
- `.omo/debt/items/*.yaml` are the canonical debt objects
- `state/system.yaml` carries only derived debt summary fields and pointers
- `.omo/debt/dashboard/current.yaml`, `.omo/debt/review-queue/current.yaml`, `.omo/debt/reviews/current.md`, `.omo/debt/action-packet/current.yaml`, and `.omo/debt/action-packet/current.md` are generated outputs, not hand-edited truth
- Refresh outputs must still surface the overdue review count and next-review queue preview derived from `next_review_at`
- Dispatch is the formal surfaced handoff after refresh; publish from the refreshed truth, then sync and verify the workspace
- `.omo/debt/dispatch/current.yaml` is the machine-readable dispatch handoff surface
- `.omo/debt/dispatch/current.md` is the human-readable dispatch handoff packet
- `.omo/debt/dispatch/runs/` stores immutable dispatch run snapshots for audit and replay
- Dispatch freezes commands to dispatched_at so operators execute the surfaced packet against a stable timestamp, not a later local clock
- Duplicate timestamp dispatch attempts fail closed with a duplicate timestamp / no overwrite policy; rerun with a new `--now` value instead of replacing an existing surfaced handoff
- `.omo/debt/review-queue/current.yaml` is the operator-facing queue surface for due-now work, escalation candidates, upcoming work, and unscheduled debts
- `.omo/debt/action-packet/current.yaml` is the machine-readable next-action surface; `.omo/debt/action-packet/current.md` is the human-readable operator packet
- `.omo/debt/action-packet/current.yaml` remains the owner-neutral next-action surface
- `.omo/debt/owner-routing/current.yaml` is the machine-readable owner execution surface
- `.omo/debt/owner-routing/current.md` is the human-readable owner execution packet
- Action-packet lanes use deterministic first-match routing: `Revalidate Now` for stale due/escalated debts, `Schedule Now` for unscheduled debts, `Escalate Now` for overdue escalation work, `Continue Mitigation` for active mitigation that still needs follow-up, and `Watch Only` for upcoming awareness-only items
- Owner routing preserves one primary lane per debt item and adds priority flags such as `initial_review_required`, `gate_attention`, and `escalation_watch`
- Revalidate and schedule entries now publish an execution-safe command template plus a shell example so operators can fill in timestamps without editing generated files by hand
- Revalidate command template: `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id <ID> --reviewed-at <RUN_AT>`
- Revalidate shell example: `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id <ID> --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)`
- Gate-level dispatched revalidate items require approval; approval is required only for gate-level dispatched revalidate items, not every review-queue or schedule action
- Approvals are recorded at `.omo/debt/approvals/<ITEM_ID>/current.yaml` and are created with `python3 scripts/omo_debt.py approve --omo-dir .omo --id <ITEM_ID> --approved-by <OWNER> --scope execute_revalidate --approved-at <APPROVED_AT>`
- The approval seam binds the approval to the dispatch run binding for the surfaced packet and to the `execute_revalidate` scope so operators cannot replay an approval against a different handoff
- Execute only from the dispatched packet that produced the approval: a stale approval mismatch between the approval record and the current dispatch run must fail closed and require a fresh dispatch-bound approval before execution
- Dispatched `revalidate` commands now carry `--dispatch-run-ref .omo/debt/dispatch/runs/<timestamp>.yaml`; use the frozen dispatch command rather than reconstructing it by hand
- If a newer dispatch run supersedes the surfaced packet, stale dispatched commands fail closed until the operator reruns from the latest dispatch packet
- Successful dispatched execution writes immutable evidence under `.omo/debt/dispatch/executions/<RUN_STAMP>/<ITEM_ID>.yaml`
- Generate the latest run-level coordination packet with `python3 scripts/omo_debt.py campaign --omo-dir .omo`; pass `--run-ref <RUN_REF>` when you need to inspect a specific dispatch run instead of the latest one
- Campaign packets are derived from dispatch, approval, and execution facts and live at `.omo/debt/campaign/current.yaml` plus `.omo/debt/campaign/runs/<RUN_STAMP>/current.yaml`
- Campaign state meanings stay narrow in Version 1: `pending_approval` means a gate item lacks matching approval for the run, `ready_to_execute` means the run still has executable work, and `executed` means immutable execution evidence already exists for that run/item pair
- Generate the latest-run compact rollup with `python3 scripts/omo_debt.py report --omo-dir .omo`; pass `--run-ref <RUN_REF>` when you need reporting for a selected run instead of the latest one
- Reporting packets are derived from the same dispatch, approval, and execution facts and live at `.omo/debt/reporting/current.yaml` plus `.omo/debt/reporting/runs/<RUN_STAMP>/current.yaml`
- Surface boundary: dashboard = debt health, campaign = coordination detail, reporting = compact progress rollup
- Reporting is the latest-run compact rollup, not cross-run history; use it for one selected run's approval coverage and execution completion snapshot
- Approval coverage and execution completion in reporting always refer to the selected run, so operators can confirm how much of that surfaced packet is approved and how much is already executed
- Generate the cross-run history index with `python3 scripts/omo_debt.py report-history --omo-dir .omo`
- Reporting history lives at `.omo/debt/reporting/history/current.yaml` plus `.omo/debt/reporting/history/current.md`
- The history surface resolves the latest run and prior run (`latest_run_stamp` / `prior_run_stamp`) from dispatch-run identity and is the prerequisite for later diff work, including latest-vs-prior slices
- `report-history` enumerates known dispatch runs, attaches per-run reporting artifacts when present, and keeps missing reporting artifacts visible instead of silently dropping those runs
- Generate the latest-vs-prior diff with `python3 scripts/omo_debt.py report-diff --omo-dir .omo`
- Reporting diff lives at `.omo/debt/reporting/diff/current.yaml` plus `.omo/debt/reporting/diff/current.md`
- `report-diff` uses `reporting/history/current.yaml` only to select the latest/prior run pair, then re-derives both runs from dispatch, approval, and execution facts before comparing them
- If only one run exists, `report-diff` writes a valid `no_prior_run` packet instead of failing
- When a prior run exists, `summary_diff` stays compact and `owners` expands into `owners.compared`, `owners.added`, and `owners.removed`
- `owners.compared` covers shared owners only; added owners and removed owners are surfaced explicitly instead of being silently dropped
- Burndown and wider trend analytics remain deferred
- Schedule command template: `python3 scripts/omo_debt.py schedule --omo-dir .omo --id <ID> --next-review-at <NEXT_REVIEW_AT>`
- Schedule shell example: `python3 scripts/omo_debt.py schedule --omo-dir .omo --id <ID> --next-review-at 2026-06-17T00:00:00Z`
- Review packets must expose sections for `Due Now`, `Escalation Candidates`, `Upcoming Window`, and `Unscheduled Debts`

---

## 七、常见场景速查

| 场景 | 操作 |
|------|------|
| "我刚启动会话，该做什么？" | 按 §一 启动流程阅读 6 步 |
| "我想了解系统健康状态" | 读 `state/system.yaml` 的 `health_score` 字段 |
| "我想找任务做" | 查 `tasks/active/`，检查 risk_level 是否匹配你的能力 |
| "我完成了一个任务" | 任务移到 `tasks/done/`，填写 evidence，更新交付面 |
| "我要创建新文档" | 按 §五 文档创建规范选择分类 |
| "我需要查阅设计文档" | 从 `_knowledge/design/INDEX.md` 进入 `plans/` |
| "我发现了不一致" | 更新对应 SSOT，运行 `CONSISTENCY-CHECK.md` 验证 |
| "我不确定这个文件该放哪" | 查阅 `DOC-ARCH.md` 四平面映射表 |

---

## 八、反模式（不要这样做）

| ❌ 反模式 | 正确做法 |
|----------|---------|
| 在知识面文档中复制任务状态 | 使用相对路径指针引用事实面源文件 |
| 从旧快照（如 HEALTH_DASHBOARD.md）取状态 | 始终读 `state/system.yaml` |
| 直接修改 `goals/current.yaml` | 目标仅由人类修改 |
| 忘记标注文档 `freshness` 日期 | 新文档必须标注日期，90 天未更新标记 `⚠️ stale` |
| 删除旧的运行记录 | 运行记录不可删除，仅可标记 `archived` |
| 在错误的平面创建文档 | 按 §五 分类放置 |

---

*维护: 2026-05-31 · Agent 每次会话启动必读*
