---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-30
---

# ADR-0117: 撤销 P60 GOVERNANCE_MAINTENANCE 阶段 (P52 真治本)

- **Status**: ACCEPTED (撤销 P60)
- **Date**: 2026-06-30
- **Authors**: governance-team (P52 真治本路线)
- **Supersedes**: ADR-0115 (7→8 接受, 已撤销)
- **Related**:
  - `.omo/_knowledge/audits/2026-06-23-p60-implementation-closeout.md` (P60 实施)
  - `.omo/_knowledge/audits/2026-06-23-p60-governance-internalization-proposal.md`
  - `.omo/_knowledge/decisions/0054-p60-governance-internalization.md`
  - ADR-0116 (Tier 1 vs Tier 2 反思)

## Context and Problem Statement

P60 (2026-06-24, commit `87b7914`) 在 model-driven `LifecycleStage` enum
新增第 8 阶段 `GOVERNANCE_MAINTENANCE`, 含完整 entry/exit_criteria 和
STANDARD_STAGES 中 STAGE-GOVERNANCE-MAINTENANCE entry。

P52 渐进 (2026-06-30, ADR-0115) 接受 P60, 测试断言同步 7→8, 加注释
"8 阶段是当前规范, 7 是 P60 前的临时态"。

P52 真治本反思 (ADR-0116) 发现: **P60 错塞 X 进 L2 业务阶段**, 违反
5+4+1+1 分层。

## Decision

### 1. 撤销 GOVERNANCE_MAINTENANCE 阶段

`projects/model-driven/src/model_driven/mof/m3_extended.py`:
- `LifecycleStage.GOVERNANCE_MAINTENANCE` enum value 撤销
- `STANDARD_STAGES` 中 `STAGE-GOVERNANCE-MAINTENANCE` entry 撤销

### 2. 测试同步恢复 8→7

- `tests/test_lifecycle.py`: `len(tracker.stages) == 7`, `total_stages == 7`
- `tests/test_m3_extended.py`: `len(list(LifecycleStage)) == 7`, `STANDARD_STAGES == 7`

### 3. 治理维护职责归 X 轴 (不删, 转移)

| 阶段 | 归处 |
|------|------|
| frontmatter 覆盖率维护 | `aetherforge/lint-tools` |
| drift LOW 维度监控 | `aetherforge/x-mof-drift-checker` |
| mof-version vs git commit 闭环 | `aetherforge/mof-bridge-sync` |
| linter 维度饱和预警 | `aetherforge/ado-tooling` |
| 治理就绪度 5 维度评估 | `omo/governance-agent` |

跨切所有 Y 阶段 (L0/L1/L2/L3/I0) 的治理维护, 走 X 轴框架维护,
不混入 L2 业务 LifecycleStage。

### 4. ADR-0115 撤销

ADR-0115 "接受 P60" 已废, 标 "Superseded by ADR-0117", 保留供历史追溯。

## Rationale

### 5+4+1+1 分层
- L0/L1/L2/L3/I0 是 Y 轴 (流水线)
- X (aetherforge/c2g/bus-foundation/...) 是横切所有 Y 阶段的框架
- governance 横切所有 Y 阶段, 属于 X 不属于 L2

### 撤销 vs 接受
- P60 设计理由 (稳态治理闭环) 合理, 但塞入位置错
- 撤销位置, 保留职责 (X 轴维护)
- 类似 "事务性" vs "业务性": 治理是事务, 不是业务阶段

## Consequences

**正向**:
- model-driven 7 阶段语义恢复, 跨包影响小
- 治理职责归 X 轴, 单一可发现入口
- ci-python-coverage.yml model-driven 仍 green
- 治本: 错误前提 (X 错塞 L2) 真正清除

**负向**:
- P60 实施撤销 (PR/commit `87b7914` 实际保留作历史), 公开承认
- ADR-0115 撤销 (写文档) 增加 metadata 成本
- 测试 7→8→7 来回改, 需 cross-package grep 审计

## Alternatives Considered

### A. 接受 P60, 不撤销
- **拒绝**: 治本要求撤错误前提

### B. 保留阶段, 改语义为 "advisory"
- **拒绝**: enum 改 advisory 复杂度高, 不解决 X 错塞根本

### C. 单独 model-driven 移除, 跨包不审计
- **拒绝**: 跨包 grep 必要, 防止引用残留

## References

- P60 实施 commit: `projects/model-driven 87b7914` (保留作历史, 标记 superseded)
- ADR-0115 (7→8 接受, 已 superseded)
- ADR-0116 (Tier 1 vs Tier 2 反思)
- 治理维护 X 轴归属: `projects/aetherforge/` (drift/lint tools)
