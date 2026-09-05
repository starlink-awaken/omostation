---
id: ADR-0422

title: "ADR-0422: D4 逃生口固化 — 权限类 vs fingerprint 债"
status: archived
lifecycle: spec
owner: governance-team
date: 2026-08-21
last-reviewed: 2026-08-21
tags: [d4, escape-hatch, swarm, gac]
related:
  - ADR-0220 (swarm coordination D4)
  - BET-Y1Q1-T1-07 (git-shim / swarm-git)
  - BET-Y1Q3-T1-09
type: ssot
---

# D4 逃生口固化 — 权限类 vs fingerprint 债

## Context and Problem Statement

D4 已有白名单 + `.omo/_delivery/swarm-escape/` 台账，但台账是只写不读。66 条记录全是 `ci_local_skip`：44 次用 `submodule-reachability-partial-worktree` 跳过 **ci-local-fast**（reachability 并不被 `CI_LOCAL_SKIP` 跳过），22 次 agent 使用 `emergency-human-hotfix` 而 YAML `requires_human` 未执行。预存门禁失败因此无人认领。

## Decision Drivers

- 逃生口必须保留（并发误伤、人类急救）
- 不能靠 prompt 自觉
- 新门禁必须 shadow → fail，避免 ADR-0380
- AGENT-BRIEF §1.4 禁止全量 submodule init
- ruff / layer-call 已有内层回归基线，禁止再抄一份到跳过层

## Considered Options

1. 只给 escape_id 加配额
2. 只按失败 fingerprint 治理、取消权限类
3. **权限类 + fingerprint 债**（采用）

## Decision Outcome

`escape_id` 是权限类。债的身份是 `(surface, check_id, signature)`。`CI_LOCAL_SKIP` / wrapper `--no-verify` **先跑预检再决定是否跳**。`emergency-human-hotfix` 在 `AGENT_ID` / shim / swarm-git 路径立即 fail-closed，一次性 `SWARM_ESCAPE_TOKEN` 例外。Skip policy Wave 1 为 `mode: shadow`（would-block 记日志、不 exit 1），人类口除外。`partial-worktree` 只能跳 `uninitialized-submodule:*`。known-debt 在 `gate-known-debt.yaml`，只准收缩。GitHub CI 本轮不接线。

## Confirmation

- `tests/test_swarm_discipline.py` 驱动 shipped `check_escape_hatch` / `overheat_signal`
- `tests/unit/gac/test_ci_local_fast.py::test_classify_*`
- `python3 bin/gac/escape-digest.py --dry-run` 聚类历史台账且 `mutated_allowlist=false`
- `.githooks/pre-push` 含 `--failures-json` + `escape-check --failures-file`
