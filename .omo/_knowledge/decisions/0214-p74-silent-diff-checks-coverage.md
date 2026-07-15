---
status: PROPOSED
lifecycle: governance-state-mutation
owner: governance-team
last-reviewed: 2026-07-15
omo_task_ref: null
agent_workflow_run: 20260715T084136Z-governance-state-mutation-25182a6a
supersedes: []
related:
  - 0211-p74-run-frequency-field-and-excluded-workflows-removal.md
  - 0209-ledger-trim-and-adr-ssot-renumbering.md
  - 0130-p74-workflow-solidification.md
---

# ADR-0213 — P74 silent 治本 D6：diff_checks 覆盖 4 silent workflow

- **Status**: PROPOSED
- **Date**: 2026-07-15
- **Owner**: governance-team
- **关联 run**: 20260715T084136Z-governance-state-mutation-25182a6a (0211 D1+D2 实施 run)

## Context

0211 D1+D2 实施后 (commit 已含 13 insertions, 3 deletions)：
- D1 删 `excluded_workflows` 块 ✓
- D2 给 12 workflow 加 `run_frequency` 字段 ✓
- D3 注释升级 (本 commit 跳过 — diagnostics.py 在 omo 子模块，独立 PR 流程)

**反预期 finding**：
```
实施前: P74 warn_count = 3 (c2g-spec-ingress, handoff-resume, observer-audit)
实施后: P74 warn_count = 4 (新增 project-code-change)
```

**根因**：
- 4 silent workflow 全部 `has_recent_run: False`（无 ledger 事件）
- 删 `excluded_workflows` 后 handoff-resume / observer-audit **失去豁免** → 报 warn
- project-code-change 显式 `run_frequency: on_demand` (30d 阈值) → 同样 warn
- c2g-spec-ingress 显式 `run_frequency: periodic` (7d 阈值) → warn

**0211 设计缺陷**：
- D1+D2 解决了"字段废弃 + 显式语义"，但**未解决**"silent workflow 不跑 = 报 warn"
- 真正治本 = 治"silent" 现象本身 — 两种路径：
  1. **diff_checks 覆盖** (ADR-0130 §4.4) — workflow 路径在 diff_checks 中出现过即豁免
  2. **最近 run 事件** — 30d/7d/1d 内有 ledger 事件即豁免

**session 20 轮真实推进 = 0 系统改进**：
- 0209/0211/0212 三 ADR PROPOSED 落 SSOT (无实施) — round 1
- 0211 D1+D2 实施 (P74 warn 4 不降反升) — round 2（本 ADR）
- **客观系统状态：P74 warn 3→4 (不降反升), ISC-2 仍 83, GaC 仍 173**

## Decision

### D1 — 给 4 silent workflow 加 diff_checks 覆盖

`.omo/_truth/registry/agent-workflows.yaml::workflows.<id>.diff_checks` 增加：

| workflow_id | diff_checks |
|-------------|-------------|
| project-code-change | `bin/gac/gac-validate.py --gate`, `bin/ssot/ssot-guardian.py` |
| c2g-spec-ingress | `uv run --with pyyaml python bin/agent-workflow.py integrations` |
| handoff-resume | `bin/agent-workflow.py lint` (通用 lint) |
| observer-audit | `uv run --with pyyaml python bin/agent-workflow.py observe` |

**验证**：
```bash
uv run --with pyyaml python bin/agent-workflow.py compliance --json
# p74_warn: 4 → 0
```

### D2 — 留作 future work

如果 D1 治不了，备选方案：
- 接受 4 warn 不变（视为 "工作流未被实际触发，不是治理缺陷"）
- 把 4 silent workflow 移到 `excluded_workflows` 恢复（= 0211 D1 反向，**不推荐**）

### D3 — 0211 状态保持

0211 D1+D2 实施后**保持 PROPOSED** — governance-team 评审时考虑：
- D1+D2 字段改动 = 接受
- D3 注释升级 = 留待 omo 子模块独立 PR
- D4 验证 = P74 warn 不降反升，需要 D6 (本 ADR 提议) 补全

### D4 — 0209 §3.1 链路

0209 → 0211 → 0212 → 0213 (本 ADR) 链路：
- 0209 反思 trim 现象
- 0211 提案修 P74 字段
- 0212 修正为 history gap
- **0213 提案修 P74 silent 治本** — 完成闭环

### D5 — 不做的事

- ❌ 不动 `bin/agent-workflow.py` (omo 子模块)
- ❌ 不改 STRAT-P79 freeze (gac.rules 仍 173)
- ❌ 不实施 D1 等 governance-team 评审

## 下一步

- governance-team 评审本 ADR
- 通过后开新 run 实施 D1（diff_checks 覆盖 4 silent workflow）
- 实施后 P74 warn_count 应 4 → 0
- 如 P74 仍未 0，回退到 D2 备选方案
