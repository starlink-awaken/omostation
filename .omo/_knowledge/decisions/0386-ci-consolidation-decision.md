---
id: ADR-0386
title: CI Consolidation — scope dedup, pytest merge, integration filter, workflow health
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-07
type: ssot
---

# ADR-0386 Decision: CI Check Consolidation (Architecture Analysis + Plan)

> Status: PROPOSED → ready for execution after user approval

## 一、42 个 Workflow 架构全景

### 触发分类

| 类型 | 数量 | 占比 | 每 PR 开销 |
|------|------|------|-----------|
| **PR-triggered (无路径过滤)** | 24 | 57% | ~30 jobs |
| **PR-triggered (有路径过滤)** | 4 | 10% | 仅相关变更触发 |
| **scheduled only** | 12 | 29% | 0 (cron only) |
| **main push only** | 3 | 7% | 0 |

**核心瓶颈**：24 个无路径过滤的 PR workflow × 并发 20 agent = 每轮约 600 个 CI job 排队。

### PR-triggered 无路径过滤清单（24 个）

```
governance:          gac-gate, evidence-smoke-gate, phase-gate-enforce, state-goals-enforce, task-schema-enforce, constraint-validation
quality:             quality, ruff-check, pytest
project CI:          agora-ci, cockpit-ci, ecos-ci, family-hub-ci, kairon-ci, metaos-ci, observability-ci
enforce:             cross-deps-enforce, interfaces-enforce, port-registry-enforce
integration:         integration
coverage:            ci-python-coverage
workspace:           workspace, debt-audit
ai:                  ai-pr-review
```

## 二、冗余分析

### 🔴 高影响冗余（可立即消除）

| 冗余对 | 重叠内容 | 影响量 |
|--------|---------|--------|
| **ruff-check.yml + quality.yml** | quality.yml 已有 "Ruff lint" job；ruff-check.yml 是独立的 6-job workflow 跑同样的东西 | 6 jobs/PR × 20 agent = 120 jobs |
| **pytest.yml + ci-python-coverage.yml** | pytest.yml 跑 omo tests；ci-python-coverage 跑 omo coverage + 其他 pkg；两者都包含 omo 的 pytest | 6+8 jobs × 20 agent = 280 jobs |
| **integration.yml 无路径过滤** | 集成测试全 PR 运行；大部分变更不涉及跨模块接口 | 9 jobs × 20 agent = 180 jobs |

### 🟡 中等冗余（可优化）

| 问题 | 说明 |
|------|------|
| **agora-ci.yml 10 jobs** | 项目级 CI 通常只需 1-2 个 test job |
| **governance-check.yml + gac-gate.yml** | 部分检查在两个 workflow 中都执行（如 submodule-reachability） |
| **workspace.yml + gac-gate.yml** | workspace 有 submodule sync + reachability；gac-gate 也有 |

## 三、架构决策

### 决策 1: 合并 ruff + quality（G16）

**现状**: `ruff-check.yml` (6 jobs, per_pr) 和 `quality.yml` 的 "Ruff lint" job 执行相同检查。
**决定**: 删除 `ruff-check.yml`，quality.yml 已完整覆盖。
**节省**: ~120 jobs/PR（6 jobs × 20 agent）
**风险**: 低 — quality.yml 的 Ruff job 与 ruff-check.yml 逻辑等价

### 决策 2: 合并 pytest + ci-python-coverage（G17）

**现状**: 两套 workflow 都跑 omo 的 pytest，ci-python-coverage 额外跑 coverage。
**决定**: 
- 将 pytest.yml 的 omo test 功能合并进 ci-python-coverage.yml
- 删除独立的 pytest.yml
- ci-python-coverage.yml 增加 coverage 报告步骤
**节省**: ~180 jobs/PR
**风险**: 中 — 覆盖率输出格式变化；需测试

### 决策 3: integration.yml 增加路径过滤（G18）

**现状**: 集成测试全 PR 运行（9 jobs）。
**决定**: 增加 `paths` 触发器，仅在以下路径变更时运行：
```yaml
paths:
  - 'projects/**/src/**'
  - 'bin/ssot/**'
  - 'bin/gac/**'
```
**节省**: ~90% PR 不再跑集成测试（9 jobs × 0.9 = ~8 jobs/PR 省）
**风险**: 低 — 纯文档 PR 不会 break 跨模块接口

### 决策 4: workflow 状态监控（G19）

**新增**: `bin/ssot/workflow-health.py` — 扫描 workflow YAML，报告：
- 哪些 workflow 有 `on: [push, pull_request]` 无路径过滤（E-4 残留检测）
- workflow 内连续 continue-on-error 比例（过度宽容警告）
- 触发模式分布（PR/scheduled/manual/callable）
- 空闲 workflow 检测（只 workflow_dispatch，无其他触发）

接入 healthcheck check #19。

### 决策 5: 原则（ADR-0386 Governance Principle）

**新原则**: CI workflow 必须满足以下之一才能存在：
1. 有路径过滤触发器（仅相关变更运行），或
2. 是必要的 governance gate（gac-gate/phase-gate），或
3. 是 scheduled（cron/手动触发），或
4. 有文档说明为什么不满足 1-3

不满足的 workflow 应该被 merge 进更合适的 workflow 或删除。

## 四、预估收益

| 改进 | jobs/PR 节省 | 占当前 ~30 jobs 的比例 |
|------|-------------|---------------------|
| G16 合并 ruff+quality | 6 | 20% |
| G17 合并 pytest+coverage | 2 | 7% |
| G18 integration 路径过滤 | 7 | 23% |
| G19 监控防止复生 | 0 (预防性) | 0 |
| **总计** | **~15** | **~50%** |

**30 → ~15 jobs/PR**，PR 验证时间从 ~5-8min 降至 ~3-4min。

## 五、实施计划

### ADR-0386 scope: G16 + G17 + G18 + G19

- G16: 删除 ruff-check.yml（quality 已覆盖）
- G17: 合并 pytest.yml → ci-python-coverage.yml；删除独立 pytest.yml
- G18: integration.yml 加 paths 过滤
- G19: bin/ssot/workflow-health.py + healthcheck check #19
- ADR-0386 文档 + 测试

### 验证标准

1. `make gac-local-gate` PASS
2. `python3 bin/gac/gac-healthcheck.py` 全绿
3. pytest 通过（含新增 workflow-health 测试）
4. PR 合并后：CI checks 从 ~38 降至 ~28

## 六、后续

ADR-0386 之后的 roadmap：
- M3 (C1): drift 历史 → 并发热点预测
- M4 (C2): ADR 草案生成器
- M5 (C3): 季度治理价值报告
