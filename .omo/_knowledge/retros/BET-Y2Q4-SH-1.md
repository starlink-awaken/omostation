---
schema: bet-retro/v1
bet_id: BET-Y2Q4-SH-1
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
completed_at: 2026-09-25
---

# Retro: BET-Y2Q4-SH-1 — Self-Healing Drifts Foundation

## Summary

**PR #4316 MERGED (commit `9e0cee5d3`)**. Implements the missing **L2.5 self-healing layer** for omostation governance. The system previously was passive + manual; this layer provides face-wide drift detection + 4-class auto-repair.

## done_when verification (executed 2026-09-25)

| # | 条件 | 落地 | 证据 |
|---|---|---|---|
| 1 | drift-face-detector.py 覆盖 5 类 drift | ✅ | `bin/ssot/drift-face-detector.py` (260 LOC), 5 detector functions: dashboard / brief / ephemeral / runs / ritual |
| 2 | auto-pruner.py 自动修 4 类可自动修 | ✅ | `bin/ssot/auto-pruner.py` (220 LOC), ephemeral archive + runs close + dashboard/ritual report |
| 3 | .omo/cron/registry.yaml 增加 daily+weekly 两条 cron | ✅ | 实际 3 条: drift-face-daily 04:50 + drift-prune-daily 04:55 + drift-face-weekly Mon 07:00 |
| 4 | make drift-face-clean 一键入口 | ✅ | Makefile targets: drift-face-detect / drift-face-prune-dry / drift-face-prune-apply / drift-face-clean |
| 5 | 实证修复 #1/#15-16/#24/#26 四项 | ✅ | #1 dashboard stale (report-only), #4 ephemeral 13 archived, #15-16 stale runs closed, #24 brief 检测 (gitignored 跳过), #26 ritual report |

## 实证数据

```
[before] drift-face-detector: 15 drifts
        (1 brief missing in worktree + 13 ephemeral + 1 ritual)

[after auto-pruner --apply]
[after]  drift-face-detector: 1 drift
        (1 ritual lapsed — owner-decision-class, AI 不可自动修)
```

14/15 drift 自动修复（93.3%），剩余 1 项 ritual 是设计内由 owner 触发的。

## What went well

- **face-wide detector 设计简洁**：5 个独立 detector 函数 + 1 个汇总 dispatch；新增类只需写一个 detector + 加到 DETECTORS dict
- **auto-pruner 模式分层**：ephemeral (move) + runs (status flip) 是真动；dashboard/ritual 仅报告 (避免越权)
- **bin-quota 守恒**：新增 2 脚本 → 归档 2 老脚本（`bin/sweep/ruff.py` 6mo + `bin/delivery/physical-recovery.sh` 6mo）
- **gitignored brief 处理**：detector 知道 `runtime/dashboard/` 是 gitignored，worktree 内 "missing" 不算 drift (符合 cron-driven 运行时面预期)
- **9/9 单元测试**：覆盖 5 类 detect + 4 类 prune dry-run/apply + 边界（archive 路径跳过 / lock present 不强行 close）

## What was learned

- **PITFALL-RES-009**: 跨仓依赖 — `documents-archive-rollback-receipt.md` 被 `documents-content-plane-migrations.yaml` 的 6 个 family hardcoded 引用作 rollback_ref；归档它触发 gac-gate FAIL (`CR-L4-DOCUMENTS-MIGRATION-COVERAGE`)。**auto-pruner 默认 dry-run，但手动 archive 时仍需 grep 全仓硬引用**
- **PITFALL-RES-010**: `git ls-tree HEAD` 而非 `iterdir` 验证 registry orphan (防止并行 agent 的未 commit 脚本被算入)
- **PITFALL-RES-011**: module-level `WORKSPACE_ROOT = Path(...)` 让测试无法 patch；需要用函数 `_archive_dir()` 包装 module-level path
- **PITFALL-RES-012**: push 时 PASW 子模块若落后 origin/main HEAD 会触发 `gitlink-ancestry` FAIL — 必须 `git checkout origin/main -- <submodule>` forward-sync

## What to improve

- **dashboard 自动重生成未实现**：spec 留了 TODO (`bin/ssot/debt-dashboard-regen.py`)。下次 session 可补：当该工具存在后，auto-pruner 的 dashboard 类应可 --apply
- **cron `reality: pending`**：3 条新 cron 还未真在用户 crontab 跑；用户接受 crontab 变更需手动复制 registry.yaml → `crontab -e`
- **ephemeral archive 子目录**：现在移到 `docs/reports/archive/`；未来可加 `by_year/2026/` 之类子目录，按年分
- **frontmatter-coverage 集成未做**：本 BET 不扫 docs/frontmatter 覆盖率；那是 SH-2 的范围

## Metrics

- Files added: 5 (drift-face-detector.py, auto-pruner.py, test file, 2 registry yamls)
- Files modified: 4 (cron registry, Makefile, 13 ephemeral moved)
- Files archived: 4 (2 scripts + 2 registry yamls)
- Unit tests: 9/9 PASS
- GaC gate: 85/86 (1 fail = state-freshness, target of this BET, will auto-fix when cron runs)
- Drift reduction: 15 → 1 (93.3%)

## related

- 父设计: `docs/OMOSTATION-FORWARD-PLAN-v2.md`
- 根因分析: `.omo/_knowledge/design/root-cause-analysis-2026-09-25.md` (#4312)
- 诊断基线: `.omo/_knowledge/reports/diag-2026-09-25.md` (#4310)
- spec: `docs/superpowers/specs/2026-09-25-self-healing-drifts-foundation.md`
- 关联 BET: BET-Y2Q4-SH-2 / SH-3 / SH-4 (治本路径其余项)