---
status: active
lifecycle: ssot
owner: governance-team
last-reviewed: 2026-06-24
---

# SSOT Guardian — 治理状态漂移防护机制

> **范围**: `.omo/state/system.yaml`、`.omo/goals/current.yaml`、`.omo/tasks/registry/INDEX.md`
> **目标**: 防止派生状态与真源目录再次漂移,避免 Agent/人类基于过期计数做决策.
> **真源**: `tasks/{active,planned,done}/` 顶层 `*.yaml` 文件、`system.yaml` 运行时状态、`goals/current.yaml` 目标状态.

## 1. 检测项

| ID | 检测项 | 真源 | 派生/对比面 | 严重度 |
|---|--------|------|------------|--------|
| SG-01 | Task 计数漂移 | `tasks/{active,planned,done}/*.yaml` | `system.yaml` 的 `completed_tasks` / `planned_tasks` / `active_tasks` / `total_tasks` | high |
| SG-02 | `current_wave` 不一致 | `system.yaml:current_wave` | `goals/current.yaml:current_wave` | medium |
| SG-03 | INDEX.md 过时 | `omo state sync-tasks` 输出 | `.omo/tasks/registry/INDEX.md` 中的计数与列表 | medium (手动维护) |

## 2. 工具

**脚本**: `bin/ssot-guardian.py`

```bash
# 检测模式 — 有漂移返回 1
python3 bin/ssot-guardian.py

# 自动修复模式 — 修复白名单字段并发事件
python3 bin/ssot-guardian.py --auto-fix --emit
```

**自动修复范围**:
- 调用 `omo state sync-tasks` 同步 `system.yaml` task 计数.
- 将 `goals/current.yaml:current_wave` 同步为 `system.yaml:current_wave`,并更新 `last-reviewed`.

**不会自动修复**:
- `goals/current.yaml` 中 goals 列表的进度/状态(需人类或 c2g BET 流程).
- `divergence_flags` 的语义判定(需人类 review).
- `INDEX.md` 的内容(派生文档,每次大变更后手动重写或按模板更新).

## 3. 集成

### 3.1 Pre-commit Gate

`.pre-commit-config.yaml` 中已注册 `ssot-guardian` hook:

```yaml
- id: ssot-guardian
  name: SSOT guardian (task count + current_wave drift detection)
  entry: python3 bin/ssot-guardian.py
  language: system
  pass_filenames: false
  stages: [pre-commit]
```

- 检测模式运行,**不自动修复**.
- 若检测到漂移,阻塞提交,并提示运行 `python3 bin/ssot-guardian.py --auto-fix`.

### 3.2 每日 Cron Auto-fix

Cron ID: `e78ec298`
Schedule: `17 7 * * *` (每天 07:17)

每日任务:
1. `python3 bin/ssot-guardian.py --auto-fix --emit`
2. `omo governance audit`
3. 若只修改了 `.omo/state/`、`.omo/tasks/registry/INDEX.md`、`.omo/goals/current.yaml`,自动提交 `chore(ssot): daily guardian auto-sync`.
4. 若出现意外文件改动,停止并发出 `ssot_guardian_auto_commit_blocked` 事件.

## 4. 事件

Guardian 运行时发出以下事件到 `.omo/_knowledge/omo-events.jsonl`:

- `ssot_guardian_run` — 每次运行,含 `issues`, `unresolved_count`, `auto_fix` 字段.
- `ssot_audit_divergence_found` — 发现新漂移(人工审计时).
- `tasks_registry_index_updated` — INDEX.md 更新.

## 5. 人工流程

当 pre-commit 被阻塞时:

```bash
# 1. 查看漂移详情
python3 bin/ssot-guardian.py

# 2. 自动修复(仅限白名单字段)
python3 bin/ssot-guardian.py --auto-fix

# 3. 检查修复结果
omo goal status
omo state show
omo governance audit

# 4. 提交
# (若自动修复涉及 goals/current.yaml,需在 commit message 中说明理由)
```

## 6. 例外与红线

- **不得** 在 `bin/ssot-guardian.py` 之外新增直接写 `system.yaml` / `goals/current.yaml` 的脚本.
- **不得** 让 guardian 自动修改 `divergence_flags` 的语义内容(只能人类或 OMO governance 流程判定).
- **不得** 自动 bump 子模块指针; cron auto-commit 只提交 `.omo/` 内 SSOT 文件.

## 7. 历史

- 2026-06-24: 机制建立,修复 `INDEX.md` 47/167/54 过期计数、`current_wave` W1/W3 不一致、`missing_goal_tasks:6` 过期 flag.
