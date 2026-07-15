---
status: ACCEPTED
lifecycle: governance-state-mutation
owner: governance-team
last-reviewed: 2026-07-15
omo_task_ref: null
agent_workflow_run: 20260715T080633Z-governance-state-mutation-1f020416
supersedes: []
related:
  - 0209-ledger-trim-and-adr-ssot-renumbering.md
  - 0130-p74-workflow-solidification.md
---

# ADR-0211 — P74 `excluded_workflows` 字段废弃 → `run_frequency` 落地

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team
- **关联**: ADR-0209 附录 A · A5 (P74 失衡议题)

## Context

ADR-0209 落 SSOT (#386) 后，本 ADR 处理**附录 A 第 5 条**（原 A5 提案 `recent_window_minutes` 失衡假设在源码层证据下升级为更精确根因）：

1. `.omo/_truth/registry/agent-workflows.yaml` `silent_workflow_policy.excluded_workflows` 字段声明 `handoff-resume` + `observer-audit`
2. `projects/omo/src/omo/workflow/diagnostics.py:388` 注释明确写：  
   `# run_frequency replaces excluded_workflows:`
3. `diagnostics.py:448` 只读 `workflow.run_frequency`，**不再读** `silent_workflow_policy.excluded_workflows`
4. 结果：handoff-resume / observer-audit 在 `excluded_workflows` 列表但仍报 silent warn（属"声明失效"）
5. 同时 P74 静默判定使用 `run_frequency` 阈值（on_demand=30d / periodic=7d / continuous=1d），但 yaml 里**所有 workflow 都缺 `run_frequency` 字段**——全部默认 `on_demand`
6. 双重叠加 → 3 silent workflow (c2g-spec-ingress / handoff-resume / observer-audit) 持续 warn

0209 §D2 假设 2（`omo state sync` 把 `_delivery/agent-workflows/` 误判为派生面 trim ledger）也部分支撑：ledger 丢失事件 → `has_recent_run: False` → 静默判定失真。

## Decision

### D1 — 删除 `excluded_workflows` 字段

`.omo/_truth/registry/agent-workflows.yaml` 删除 `silent_workflow_policy.excluded_workflows` 块（line 87-89），保留 `warn_after_days: 30`。

**理由**：字段已废弃不读，保留是"假绿防线"——给读者错误的"已声明"印象。删除是治本。

### D2 — 给所有 workflow 加 `run_frequency` 字段

`.omo/_truth/registry/agent-workflows.yaml::workflows.<id>.run_frequency` 必填，默认值（按语义）：

| workflow_id | run_frequency | 阈值 | 理由 |
|-------------|---------------|------|------|
| project-doc-change | on_demand | 30d | 文档变更按需触发 |
| project-code-change | on_demand | 30d | 代码变更按需触发 |
| governance-state-mutation | on_demand | 30d | 治理 mutation 按需触发 |
| c2g-spec-ingress | periodic | 7d | 外部 spec 周期性 ingress |
| mof-model-change | on_demand | 30d | 元模型变更按需 |
| mof-state-bridge-audit | periodic | 7d | 桥接审计周期 |
| external-adapter-sync | periodic | 7d | 外部适配器周期同步 |
| submodule-pointer-close | on_demand | 30d | 子模块指针收口按需 |
| handoff-resume | on_demand | 30d | handoff 按需 |
| observer-audit | continuous | 1d | observer 期望常态化审计 |
| state-sync | continuous | 1d | state sync 期望常态化 |
| governance-audit | periodic | 7d | 治理审计周期 |

### D3 — 修 `diagnostics.py` 注释

`projects/omo/src/omo/workflow/diagnostics.py:388` 注释从 `# run_frequency replaces excluded_workflows:` 升级为：

```python
# P74 silent detection: workflow is silent iff has_recent_run == False
# AND has_check_coverage == False (per ADR-0130 §4.4).
# run_frequency drives warn_after threshold (on_demand=30d, periodic=7d, continuous=1d).
# Excluded workflow list has been removed in ADR-0211; rationale = no double SSOT.
```

### D4 — 验证

```bash
# 1. yaml lint
python3 -c "import yaml; d=yaml.safe_load(open('.omo/_truth/registry/agent-workflows.yaml')); assert all('run_frequency' in w for w in d['workflows'].values()); print('all workflows have run_frequency')"

# 2. compliance P74 warn_count 应从 3 → 0
uv run --with pyyaml python bin/agent-workflow.py compliance --json | python3 -c "import sys,json; d=json.load(sys.stdin); print('p74_warn:', d['p74_solidification']['warn_count'])"

# 3. governance-evolution validate
uv run --with pyyaml python bin/gac/governance-evolution.py validate --json
```

### D5 — STRAT-P79 freeze 合规

本 ADR **不新增 GaC 规则**（不改 `gac.rules`，仍 173）— 属 registry schema 字段 + 源码注释层级。不动 m3/m2 元模型。

## 不做的事

- ❌ 不动 STRAT-P79 freeze 173 (`gac.rules`)
- ❌ 不动 m3.yaml / m2.yaml 元模型（P52 守住）
- ❌ 不改 ledger 写入路径（属 ADR-0209 D2 议题，不在本 ADR 范围）
- ❌ 不实现 0209 附录 A 其他 5 条（A1 close evidence / A2 ledger self-heal / A3 omo.cli path / A4 claim_policy / A6 gac 3 类 finding）—— 留待 0212-0216 stub ADR

## 下一步

- governance-team 评审本 ADR
- 通过后并发实施（D1+D2 yaml 改 + D3 注释 + D4 验证）
- 失败回滚：git revert（变更局限 yaml + 1 处注释）
- 附录 A 其他 5 条：A1 → 0212 / A2 → 0213 / A3 → 0214 / A4 → 0215 / A6 → 0216（claim 占号待写）
