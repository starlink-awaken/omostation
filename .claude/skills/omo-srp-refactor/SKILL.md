---
name: omo-srp-refactor
description: Use when refactoring omo God Modules (omo_ingress/omo_governance_surfaces/omo_lint/omo_debt/omo_worker — all >1000 lines). Triggers on keywords: omo 拆分, God Module, SRP, omo_ingress 重构, broker 入口治理, 单一职责. 项目级 skill (projects/omo 专属, 因 omo 是 submodule 此 skill 随 omo 代码版本走).
---

# omo-srp-refactor

> **omo God Module 渐进拆分范式** — 从 omo_ingress.py 2957 行拆分实战提炼 (P60+).
> 项目级: 只适用 projects/omo (submodule, skill 随 omo git 版本).

## 适用场景

| 触发 | 场景 |
|------|------|
| omo_ingress / omo_governance_surfaces / omo_lint / omo_debt / omo_worker (>1000 行)| God Module 拆分 |
| 新增职责到 omo broker | 判断该入哪个子模块 (非堆进 omo_ingress) |
| "omo_ingress 太大" / SRP 违反 | 职责过载识别 |

## omo_ingress 职责域 (5 类, 拆分蓝图)

```
omo_ingress.py (2957 行, 52 def, 0 class — 纯函数式)
├─ 基础设施 (11 paths 函数) ─── ✅ 已拆: omo_ingress_paths.py (P60)
│   _utc_now/_timestamp_slug/_safe_doc_name/_load_yaml/
│   _delivery_root/_audit_log_path/_trail_log_path/_lock_path/
│   _registry_path/_mutation_log_path/_find_task_path/_artifact_lifecycle_fields
├─ registry 基础 ──────────── 待拆: omo_ingress_registry.py
│   _load_registry/_write_registry/_record_mutation/_register_ingress
├─ trail ──────────────────── 待拆: omo_ingress_trail.py
│   _record_trail (OmoTrailRecord)
├─ goal (4) ────────────────── 待拆: omo_goal.py
│   _goal_fingerprint/_goal_existing_fingerprint/_resolve_existing_goal/
│   create_goal/update_goal_progress
├─ doc 创建 (3) ────────────── 待拆: omo_doc_factory.py
│   create_knowledge_doc/create_standard_doc/create_audit_report
├─ registry 写入 (9) ──────── 待拆: omo_registry_writes.py
│   write_capability_registry_bundle/write_manual_capabilities/
│   create_skill_manifest/write_discovery_registry/write_system_projection_fields/
│   write_usage_accounting/write_task_center_freshness/
│   write_task_center_control_decision/update_governance_overlay_state
└─ task 生命周期 (~20) ─────── 待拆: omo_task_lifecycle.py (最大核心, 最后拆)
    create_planned_task/create_blocked_task/complete_task/
    promote_task_to_active/revert_task_to_planned/yield_task_to_planned/
    archive_done_task/record_task_consensus/request_task_promotion_approval/
    repair_task_promotion_approval/record_task_contract_request/
    route_self_evolution_to_remediation/update_*_evidence_paths/
    normalize_legacy_planned_task
```

## 渐进拆分纪律 (CR-ENG-SRP-INCREMENTAL-01)

**顺序强制** (低风险先, 核心后):
1. ✅ paths (纯函数, 无逻辑) — 已拆
2. 🔲 registry 基础 (load/write/mutation)
3. 🔲 trail (单函数 + OmoTrailRecord)
4. 🔲 goal (4 函数, 紧凑)
5. 🔲 doc 创建 (3 函数)
6. 🔲 registry 写入 (9 函数)
7. 🔲 task lifecycle (~20 函数, **最大, 最后**)

**每步 5 步** (地基不过别盖楼):
```bash
# 1. Write 子模块 (移函数 + import)
# 2. Edit omo_ingress: 加 from .子模块 import + 删原函数 (一个 Edit, 避免中间 redefinition)
# 3. ruff check --fix . (删 unused import: 移走后原 import 可能 unused)
# 4. import 验证: uv run python -c "from omo.omo_ingress import create_goal; from omo.子模块 import _x"
# 5. omo 全测试: uv run --directory projects/omo pytest -q
```

## 拆分判定 (何时抽子模块)

| 信号 | 动作 |
|------|------|
| 一组函数共享主题 (paths/goal/doc/registry/task) | 抽子模块 |
| 单文件 > 1000 行 | 拆分候选 |
| 新增职责 | 进对应子模块 (非堆 omo_ingress) |
| 函数被外部 import (public) | 留 omo_ingress (re-export) 或移 + 改调用方 |

## 外部调用方 (拆分前必查)

```bash
# 谁从外部 import omo_ingress (public 函数, 不能随便移)
grep -rn "from omo.omo_ingress import" projects/ --include="*.py" | grep -v omo_ingress.py
```

**规则**: 私有 `_` 函数只 omo_ingress 内用 → 可自由移; public 函数 (create_*/write_*/complete_* 等) 外部 import → 移后 omo_ingress 保留 re-export 或改调用方。

## 失败模式 (避免)

| 失败 | 后果 | 避免 |
|------|------|------|
| 一次大拆 (多职责) | 测试大 break, 难定位 | 渐进, 单职责一步 |
| 加 import 不删原函数 | redefinition (F811) | 一个 Edit 同步 (import + 删) |
| 删函数不查外部 import | 调用方 ImportError | 先 grep 外部引用 |
| ruff unused import 没清 | ruff check failed (pre-commit 拦) | 每步 ruff --fix |
| 只 import 验证不跑全测试 | 逻辑 break 漏 (import OK ≠ test 过) | 必跑 omo pytest |

## 关联

- **L0 约束**: `CR-ENG-SRP-INCREMENTAL-01` (渐进拆分纪律)
- **workspace skill**: `governance-phase-orchestrator` (RISE 循环 + 通用工程纪律)
- **实战经验**: omo_ingress paths 拆分 (2957→~2890, 2026-06-24)
- **God Module 全景**: omo 5 个 >1000 行 (ingress 2957 / governance_surfaces 1744 / lint 1477 / debt 1072 / worker_promotion 1045)

---

*omo 项目级 skill · 2026-06-24 · God Module 渐进 SRP 拆分范式 · 随 omo submodule 版本*
