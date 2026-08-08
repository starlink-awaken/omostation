---
id: ADR-0396
title: CI 净红收官 — surfaces 注册 + state sync 修复 + task schema 合规
status: ACCEPTED
lifecycle: ACTIVE
owner: governance-team
last-reviewed: 2026-08-08
---

# ADR-0396 Decision: CI 净红收官

> 承接 ADR-0395 (CI 平面净红收官). 本轮清理 main 上剩余的 governance-check 红点:
> 1. `.omo/` 未注册顶层目录 (notepads/start-work) → interface-check governance surfaces
> 2. verify-omo.sh 引用已移除的 scripts/sync_omo_state.py → governance-verify [1/5]
> 3. kos-q-growth-rolling task schema 非法 → governance-verify [3/5]

## 一、根因 (实测, 不靠猜)

### 1. notepads / start-work 未注册 (.omo 顶层目录)

| 现象 | 数据 |
|------|------|
| `omo cli governance surfaces --json` | `status: error`, `unregistered_top_levels: [notepads, start-work]` |
| `.omo/notepads/` | 已跟踪 (delegation-guardrails/decisions.md 等) |
| `.omo/start-work/ledger.jsonl` | 已跟踪 |
| registry assets | 无 OMO-NOTEPADS / OMO-START-WORK 条目 |

根因: PR #1130/#1137 引入两个新 .omo 顶层目录但未登记
`.omo/_truth/registry/omo-governance-surfaces.yaml` (P84 注册消 unregistered patterns),
governance surfaces 检查报 "unregistered top-level asset" → interface-check 红.

### 2. verify-omo.sh 引用已移除脚本

| 现象 | 数据 |
|------|------|
| governance-verify `[1/5] Syncing .omo state` | `python3: can't open file '.../scripts/sync_omo_state.py': No such file or directory` |
| scripts 子模块 main 重写 | sync_omo_state.py 仅存于废弃分支 work/interfaces-fix |
| 现行 state sync | `uv run --project projects/omo omo state sync` (ADR-0128 指定机制) |

根因: scripts 镜像子模块 main 被重写, sync_omo_state.py 从历史消失,
verify-omo.sh 仍引用旧路径 → governance-verify 在 [1/5] 直接 exit 2.

### 3. kos-q-growth-rolling task schema 非法

| 现象 | 数据 |
|------|------|
| `omo_worker task validate --all-active` | exit 1 |
| 缺失字段 | run_ref / approval_ref / review_ref / knowledge_refs / handoff_refs / source_docs / entry_gate / test_plan |
| `status: active` | 非法 — VALID_STATUSES 无 active (candidate/pending/in_progress/review/done/blocked/failed) |
| started_at | null (未开始) |

根因: PR #1132 新增 task 用了旧式字段 + 非法 status, 未过 schema 校验 →
governance-verify [3/5] task validate 红.

## 二、决策

1. **注册两个新 surface** (OMO-NOTEPADS / OMO-START-WORK), 补全 persistence/retention
   语义, 与 P84 "注册消 interface-check unregistered patterns" 一致.
2. **verify-omo.sh [1/5] 改用 `omo state sync`** — ADR-0128 指定机制,
   不再依赖 scripts 镜像子模块内的临时脚本.
3. **kos-q-growth-rolling 移到 planned/ + status pending + 补 schema 必填字段** —
   任务未开始 (started_at null), 语义上是 planned 而非 active;
   补 source_docs/test_plan/entry_gate 等使通过 schema.

## 三、不做的事

- 不碰 scripts 子模块指针 (t6-06 分支 agent/t6-06-skill-scripts 与 scripts main
  分叉, 属并发 agent 活跃工作, 其 ruff fix 合并由该 agent 完成 —
  check-submodule-pointer-drift DIVERGED 为并发残余, 非本 ADR 范围)
- 不减弱 direct-omo-io / drift 门禁语义

## 四、验证

- `omo cli governance surfaces --json` → status: ok, unregistered: []
- `omo_worker task validate --all-active/--all-planned` → exit 0
- `bash bin/ssot/verify-omo.sh` → [1/5]-[5/5] 全过, exit 0
- `tests/test_agent_workflow.py` → 36/36 pass (agcp_drift 经 omo pointer aa31c5cc 已修)

## 五、追加 (governance-verify GaC local gate 存量债)

CI 绿后 GaC local gate 暴露 3 个存量债 (非本 PR 引入), 一并清零:

1. **adr-coverage**: #1132 重编号 0388→0391 留残留副本 + 撞号 —
   删 `0388-layer-contract-direction-ssot.md`, layer-contract 重编号 0391→0397
   (duplicate_numbers=[388,391] + files_not_in_index 清零)
2. **mof-capabilities-drift**: m1_nodes 声明 1386 vs 实际 1391 → `--bump-stats`
3. **CR-CI-SURFACE-SSOT unregistered-check**: debt-audit.yml/state-goals-enforce.yml
   执行未登记检查 → ci-surfaces.yaml 登记 debt-integrity-check + current-state-coherence

验证: `make gac-local-gate` → 44 checks ALL GREEN PASS
