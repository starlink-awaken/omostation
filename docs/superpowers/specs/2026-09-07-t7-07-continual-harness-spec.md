---
status: accepted
lifecycle: spec
owner: governance-team
created: 2026-09-07
last-reviewed: 2026-09-07
title: BET-Y1Q4-T7-07 Continual Harness 证据驱动自演化与沙箱回滚
type: doc
---

# BET-Y1Q4-T7-07: Continual Harness 证据驱动自演化与沙箱回滚管道

## Context

T10-136 RLM 变量内核和 T10-137 子代理编排已落地。现有 SEMA Crystallizer（BET-Y2Q2-T6-01）实现了防踩坑信念结晶，但缺乏正向演化能力：长程任务结案后无法自动将成功经验结晶为可复用技能，也无法回滚负向演化。

## Goals

- 交付 `bin/ops/continual-harness-refine.py` 轨迹审阅与技能萃取脚本
- 交付 `projects/omo/src/omo/resident/refine_rollback.py` 回滚驱动器
- 基于执行轨迹证据（Evidence-backed）自动触发 /refine
- 结晶生成 Python 模块化技能包（Skills as Code）与环境提示词补丁
- 赋予 refinement_id，支持一键原子化 Rollback
- 异常时 5 秒内自动回滚至上一个稳定 refinement_id

## Non-Goals

- 不允许生成未经验证的高危 Python 技能包
- 不破坏已有的 70+ 核心稳定 skills 命名空间
- 不替代 SEMA Crystallizer 的防踩坑功能（正交互补）

## Technical Design

### 核心模块 1: refine_rollback.py

1. **RefinementStore** — 版本链管理
   - `create_refinement(snapshot)` — 创建新 refinement 版本
   - `rollback(refinement_id)` — 原子化回滚到指定版本
   - `list_refinements()` — 列出所有版本
   - `get_current()` — 获取当前版本

2. **SnapshotManager** — 快照管理
   - `snapshot_skill(name)` — 快照当前技能状态
   - `restore_snapshot(snap_id)` — 恢复快照
   - `diff(snap_a, snap_b)` — 对比差异

3. **AtomicRollback** — 原子化回滚
   - 两阶段提交：准备 → 提交/回滚
   - 5 秒内完成回滚
   - 失败自动重试一次

### 核心模块 2: continual-harness-refine.py

1. **TrajectoryReviewer** — 执行轨迹审阅
   - 解析 `.omo/_delivery/agent-workflows/runs/*.yaml`
   - 提取成功/失败模式
   - 识别可结晶的改进点

2. **SkillExtractor** — 技能萃取
   - 从成功轨迹中提取 Python 函数
   - 生成模块化技能包（SKILL.md + 实现）
   - 环境提示词补丁生成

3. **RefinePipeline** — 主管道
   - `trigger(task_id)` — 手动/自动触发
   - `review_and_refine()` — 审阅 + 结晶 + 安装
   - `rollback_last()` — 回滚最近一次 refinement

### 与 SEMA Crystallizer 复用

- `CorrectionLedger` → 触发计数
- `install()` + `_refresh_index()` + `hot_reload()` → skill 安装
- `SkillCandidate` → 技能候选格式

### 与 T10-136/T10-137 集成

- RLMKernel 任务结案 → 触发 /refine
- SubagentResult 成功 → 计入证据
- GaCGovernor 安全门禁 → 验证生成技能

## Write Surfaces

- bin/ops/continual-harness-refine.py
- projects/omo/src/omo/resident/refine_rollback.py
- docs/plans/3y-bet-ledger.yaml
- .omo/_knowledge/retros/BET-Y1Q4-T7-07.md

## Dependencies

- BET-Y1Q4-T10-136 (done) — RLM 变量内核
- BET-Y1Q4-T10-137 (done) — 子代理编排

## Verification

```bash
python3 bin/ops/continual-harness-refine.py --help
python3 -m pytest projects/omo/tests/test_refine_rollback.py
python3 bin/plan/bet-ledger.py lint
```

## Circuit Breaker

- 精炼生成的技能导致回归报错时，5 秒内自动回滚
- 连续 3 次 refinement 失败则暂停管道
- 单技能包大小 > 50KB 需人工审核
