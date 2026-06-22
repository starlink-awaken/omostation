---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# ADR-0008: in_progress 任务列表清理原则

- **Status**: ACCEPTED
- **Date**: 2026-06-07
- **Authors**: P37-W1 治理历史清仓
- **Supersedes**: 无

## Context and Problem Statement

P32-P36 阶段后, `.omo/tasks/planned/` 平面可能残留 19+ in_progress 任务（任务列表 #16-#34）。
这些任务是 P31-W1 CLEANUP-SHIM 等历史子任务, 已由 P33-W5 等后续工作**自动完成**, 但任务
YAML 状态未更新。

导致 task_consistency 100 但 "任务面板" 仍显示 in_progress 干扰判断。

## Decision Drivers

* 任务面板真实反映完成状态
* 不丢历史 (in_progress 已实完成的工作)
* 防债务累积
* 与 P36-W0 治理债务永久化标准一致 (`.omo/standards/task-yaml-rules.md`)

## Considered Options

### A. 保留 in_progress 不动

- 优点: 0 工作量
- 缺点: 任务面板永久混乱, 治理分数失真

### B. 全部 completed

- 优点: 面板清洁
- 缺点: 误标未实际完成的, 失信

### C. **推荐**: 按实际状态分类

- 已实际完成 (有后续产出) → `completed` + 填 `completed_at`
- 未实现 (无后续产出) → `cancelled` 或重规划为 `pending`
- 不可行 (无业务) → 删 (用 `git rm` 保留历史)
- 仍可推进 → 留 `in_progress` + 更新 `started_at`

## Decision Outcome

**Chosen option: C**, because 既保护历史 (已完成工作不被丢失) 又清晰反映状态。

### 清理原则

1. **已完成 → `completed`** + 填实际 `completed_at`
2. **可重新实施 → 改 `pending`** + 进下 wave
3. **不可行 → `cancelled`** (cancelled 字段如 yaml schema 支持)
4. **不存在 → 删** (用 `git rm` 保留历史)

### Confirmation

- [x] 批量脚本扫描所有 in_progress 任务
- [x] 按 4 类原则分类
- [x] 修订任务 YAML (P36 阶段已清仓, 0 in_progress 残留)
- [x] 跑 omo audit 验证无回归 (100.0 健康分)

### 长期维护

- 每个 Phase 收尾时跑一次 `grep -l "status: in_progress" .omo/tasks/planned/*.yaml`
- 残留 > 0 时, 触发本 ADR 决策清理
- P38 起: 任务 YAML status 字段强制 3 选 1 (completed / pending / cancelled), in_progress 仅当日内过渡态
