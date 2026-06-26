# omo_ingress_task_lifecycle.py SRP 拆分 spec (autopilot Phase 0)

> **TASK**: TASK-F7114ABA (God Module 拆分, omo_ingress_task_lifecycle 1530 行)
> **Phase**: 0 (expansion/设计)
> **日期**: 2026-06-26
> **状态**: spec 完成, 执行待启动 (srp-refactor 渐进)

## 现状

`omo_ingress_task_lifecycle.py` 1530 行, 16 函数 — omo 最大的 God Module (check-god-module 量化).
omo_ingress 已拆 8 SRP 模块 (debt/doc/goal/paths/registry/registry_writes/trail + task_lifecycle).
task_lifecycle 是剩余的最大块.

## 拆分方案 (16 函数 → 5 SRP 模块)

按职责分组, 仿现有 omo_ingress_{debt,doc,...} 模式:

### 1. omo_ingress_task_create.py (~280 行)
- `_task_payload_with_metadata` (40) — helper
- `create_planned_task` (56)
- `create_blocked_task` (167)

### 2. omo_ingress_task_complete.py (~260 行)
- `complete_task` (333)
- `update_done_task_evidence_paths` (440)
- `update_planned_task_evidence_paths` (513)

### 3. omo_ingress_task_promote.py (~290 行)
- `promote_task_to_active` (595)
- `repair_task_promotion_approval` (676)
- `request_task_promotion_approval` (790)

### 4. omo_ingress_task_revert.py (~250 行)
- `revert_task_to_planned` (885)
- `yield_task_to_planned` (1171)
- `archive_done_task` (1263)

### 5. omo_ingress_task_contract.py (~380 行)
- `record_task_consensus` (242)
- `record_task_contract_request` (967)
- `route_self_evolution_to_remediation` (1061)
- `normalize_legacy_planned_task` (1347)

## 门面改造

`omo_ingress.py` (140 行) 从 `omo_ingress_task_lifecycle` import → 从 5 新模块 import
(`# noqa: F401` re-export, 保持公开 API 不变).

## 执行策略 (omo-srp-refactor skill, 渐进)

**不用 autopilot 批量** (1530 核心代码, 批量易错). 用 srp-refactor 渐进:
1. 纯函数先 (helper: _task_payload_with_metadata)
2. 独立函数 (create/complete, 依赖少)
3. 核心后 (promote/contract, 依赖多)
4. 每步: 拆 1 模块 → import 验证 → pytest → commit

## 风险

- task_lifecycle 是 omo 任务生命周期核心 (create/complete/promote/revert)
- 拆错 break 任务流
- 必须渐进 + 每步 test (omo-srp-refactor 纪律)

## 后续

spec 完成. 执行启动条件:
- 专项 session (不混其他工作)
- omo-srp-refactor skill 激活
- 每模块拆完 ruff + pytest 验证
