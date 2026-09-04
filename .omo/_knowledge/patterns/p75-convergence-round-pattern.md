---
id: P75
title: Convergence Round Pattern — close multiple deferred ADR follow-ups in one coordinated round
created_at: '2026-08-05'
lifecycle: pattern
owner: governance-team
last_updated: 2026-08-18
---

# P75 — Convergence Round Pattern (ADR-0373, 5 方向合一)

> Adoptees: When 3+ follow-up items accumulate on the same parent's
> `next_step` field, package them into a single convergence round instead
> of one-by-one. This consolidates governance surface, testing, and
> docs churn into a single PR.

## Why

P73 / P74 已固化 "基于直觉 → 基于实证" 的工程纪律. 多个 P73-derived
follow-ups (A4/C5/D3/B2/E2) 在 ADR-0367 `next_step` 字段里挂着 30+ 天
没人做, 因为每个单一方向独立看都不算紧急. ADR-0373 把它们 package
进一个 round:

- 5 个方向同时落地, ADR 只写一份 (避免 5 份同主题 ADR).
- 单一 `diff_check` (pyright-sweep-check) 覆盖所有相关 path, 不碎片化.
- 单一 gate / hook 迭代 (CR-SWEEP-INDEX-AUTO + sweep_index_cli executor
  + lifecycle.append_ledger_event 复用), 走 5-source align 而不是 5×5.
- 单一 roadmap initiative (`sweep-tooling-convergence`), 父条目 `sweep-tooling-scaling`
  加 `convergence_provenance.superseded_by` 显式.

## When to use

- 同父 ADR 在 `next_step` 里挂了 N 个 follow-up (N ≥ 3), 都属于 "X 方向的下一阶段"
- 跨多个 SSOT 字段 (registry, gate rule, M2 enum, M1 yaml, executor enum, workflow diff_check, GitHub Actions workflow)
- 单一新工具能合并多个工具的入口 (例如 sweep_index.py 即是 INDEX 写入, 又是 sweep_index_check --check)

## How

1. **CLAIM**: 单一 ADR id round-XYZ, 单一 workflow run (governance-agent 走
   `pyright-sweep`, 因为它的 lock scopes 含 `python-type-sweep + root-gate`)
2. **ARCHITECTURE FRAME**: 单叙述覆盖多方向. 避免一个方向一份 ADR = 多份
   同主题文档, SSOT 漂移风险.
3. **5-SOURCE ALIGN**: M2 enum / governance-checks registry / gac-drift.py / gac-executor.py / M1 yaml,
   一次性同步 (`GAC_M1_SYNC_WRITE=1 python3 bin/gac/gac-m1-sync.py --sync`).
4. **PATH BOUNDARY**: `bin/sweep/` 是新工具位置, `tests/fixtures/trap_minimal.sh`
   只用于 B2 trap 测试 (不放 bin/ — 不是用户级工具).
5. **HOOK MINIMAL**: lifecycle.py 的新增 closeout hook 仅 30 行, 复用
   `append_ledger_event` 事件通道, 不重写 lifecycle.
6. **TEST ISOLATION**: B2 trap 测试 spawn bash subprocess, 用 `proc.send_signal(SIGINT/SIGTERM)`
   + `_wait_for_marker_gone()` poll, 而非 `grep text-assert` (PR #971 之前的 smoke 是 text-assert, 没真发信号).
7. **REAL-INDEX LIVE TEST**: E2 test 用真实 INDEX.md + 临时 drifted INDEX.md, 跑
   `--check` 而不是 mock (mock 反而掩盖 regression).

## Common traps

- **Mistake**: `next_step: maintain: ...` 在 YAML 里报错 (mapping values not allowed here).
  YAML 在 `:` 后面必须是 scalar 或 block; 写 `next_step: maintain. text` (用 . 替 :) 或
  `next_step: |` block scalar.
- **Mistake**: gac-m1-sync.py 默认 dry-run (F-5/ADR-0122): 写 M1 yaml 必须
  `GAC_M1_SYNC_WRITE=1`. 忘了就只 log 不写.
- **Mistake**: sweep_index.py `--out-dir` 是任意路径, `print(...index_path.relative_to(ROOT))`
  在 `/private/var/...` tmp_path 时会 `ValueError`. 用 `try/except ValueError` 兜底或 `os.path.relpath`.
- **Mistake**: agent-workflow closeout 跑完整 hook (evidence-smoke + omo state sync + KOS ingest + onto rebuild + gac-kos-sync + gac-consensus)
  超时 3-6 min. E2 test 不要走这条线; 直接用 env-driven driver subprocess 走单路径.
- **Mistake**: 一次性 5 方向落地 = 单 PR 200+ lines 改. 风险点:
  (a) M2 没更新 → mof-validate 立即 FAIL (机制 7 强校验)
  (b) M1 dry-run 默认 → 5-source 缺一, gac-drift.py 立即 FAIL
  (c) 子模块内 M2 / M1 必须 commit + bump pointer (走 submodule-pointer-close workflow)

## Required deliverable checklist

- [ ] ADR 含 5 方向 Context/Decision/Consequences/Compliance/Verification 5 段.
- [ ] `governance-checks.yaml` 加新规则 + schema `executor_enum` 更新 + lifecycle=active.
- [ ] `gac-drift.py::EXECUTOR_ENUM` 加新值.
- [ ] `gac-executor.py::EXECUTOR_PRESENCE` 加新值.
- [ ] `projects/ecos/.../m2/gac_rule.yaml::item_values` 加新值.
- [ ] `projects/ecos/.../m1/governance/GAC-RULE-CR-XXX.yaml` 由 `gac-m1-sync.py --sync` 自动生成 (写子树分子模块).
- [ ] `agent-workflows.yaml::diff_checks.pyright-sweep-check` 扩展 paths + command.
- [ ] `roadmap.yaml` 新 initiative + 父加 `convergence_provenance.superseded_by`.
- [ ] bin/sweep/** + tests/** 各加至少 1 个新测试 + 1 个真信号测试 (B2/E2).
- [ ] 32+ targeted pytest 全绿.
- [ ] `bin/adr/adr-coverage.py --json` 显示 0 missing/duplicates/mismatches.
- [ ] `bin/gac/governance-evolution.py validate --json` errors=[] warnings=[].

## Workflow registration

ADR-0373 round 走的 workflow: `pyright-sweep` (governance-agent profile).
它本来是为单个项目类型债务设计的, 但因为 lock scopes 含 root-gate +
python-type-sweep, 跨工具 sweepering 也走它, 复用 `pyright-sweep-check`
diff_check 自然 cover 所有 sweep 路径 (不用新 workflow).
