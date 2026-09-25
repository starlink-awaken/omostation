---
schema: bet-retro/v1
bet_id: BET-Y2Q4-SH-2
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
completed_at: 2026-09-25
---

# Retro: BET-Y2Q4-SH-2 — Face-Wide Frontmatter Coverage

## Summary

**PR #4328 MERGED (squash commit `fef14ccef`)**. Implements face-wide frontmatter coverage: 9 path groups × 6 required fields. **1145 files patched to 100%** coverage.

## done_when verification (executed 2026-09-25)

| # | 条件 | 落地 | 证据 |
|---|---|---|---|
| 1 | frontmatter-coverage.py 扫 9 类路径 × 6 字段 | ✅ | `bin/ssot/frontmatter-coverage.py` (260 LOC) |
| 2 | 覆盖率 matrix 输出 | ✅ | text + JSON 双格式，9×6 cells |
| 3 | --apply 模式自动 patch | ✅ | 1145 files patched in single run |
| 4 | 接入 gac-local-gate（< 80% WARN / < 50% FAIL） | ✅ | script-registry-validate 702 PASS；gate 84/86 (2 pre-existing fail = state-freshness + evidence-freshness, targets of SH-1) |
| 5 | 实证：retros 缺字段从 342 降到 ≤ 30 | ✅ | retros schema 15.9% → 100% (all 6 fields) |

## 实证数据 (before → after)

| Path | Group | Before | After |
|---|---|---|---|
| docs | 818 files | schema 0.4% | **100%** |
| .agents | 54 | schema 0% / status 23% | **100%** |
| .omo/_knowledge/retros | 511 | schema 15.9% | **100%** |
| .omo/_knowledge/reports | 2 | 0% | **100%** |
| .omo/_knowledge/decisions | 418 | schema 0% | **100%** |
| .omo/standards | 59 | schema 0% | **100%** |
| projects/*/AGENTS.md | 16 | schema 0% / status 0% | **100%** |
| projects/*/README.md | 17 | schema 0% / status 0% | **100%** |
| projects/*/GOVERNANCE.md | 13 | schema 0% / status 0% | **100%** |

**All 54 cells (path × field) ≥ 50% threshold** → 0 WARN, 0 FAIL.

## What went well

- **face-wide design**: 单一 detector + 9 path groups, 加新路径只需加 PATHS 条目
- **idempotent patches**: 已有 frontmatter 时只补缺字段 + bump last-reviewed
- **bins SKIP logic**: archive / node_modules / _delivery / templates 全跳过
- **bin-quota 守恒**: +1 (frontmatter-coverage.py) -1 (resolve-root-remote.sh 6mo offline)
- **CI lint 提前拦截**: agent-skills-lint 抓到了 multiline scalar bug，让我在 closeout 前 fix

## What was learned

- **PITFALL-RES-013**: multiline YAML scalars (`description: > ...` folded) — original regex parser 丢失续行 → SKILL.md 5-line description 被吃掉 → agent-skills-lint fail. Fix: switch `_parse_fm` + `_apply_patch_one` to use `yaml.safe_load` + `yaml.safe_dump` (preserves scalars as-is).
- **PITFALL-RES-014**: `_archive/.../bin-scripts-convergence-manifest.json` 用 `is_file()` 检查 file 存在 — 归档脚本必须同时更新 manifest entry 的 `bin` path 指向 archive，否则 audit 报 missing-bin-master
- **PITFALL-RES-015**: 大量 frontmatter patch 会让 `bin-scripts-convergence-manifest` `working_tree` evidence-smoke score 跌 (< 90 min) — commit 后会恢复
- **PITFALL-RES-016**: 并发 main racing — 4 commit PR 在 push 时常因 gitlink 落后 / 多人合入 spec normalize 而 conflict, 需要 rebase + cherry-pick + force-push

## What to improve

- **template 路径排除**: 现在跳 `/specs/templates/` 和 `/standards/templates/`，但可能漏其他 template path (e.g. `.omo/standards/templates/`). 让 walk 提供显式 `template_patterns` config
- **patcher 不生成 `description`**: 缺 description 的文件仍报"无 fm"，但不会自动填充（因无合理默认值）。下次 session 可加 description inference (从 first paragraph 取)
- **spec 文件的 fm normalize**: spec 用 `schema_version: specification/v1` 而非 `md/v1` — patcher 默认值会冲突. 已通过 `patcher rebuild via yaml.safe_dump` 保留原 schema，但 verification script 仍可能误判

## Metrics

- Files added: 3 (frontmatter-coverage.py, test, registry yaml)
- Files modified: 1145 .md files (face-wide patch)
- Files archived: 2 (resolve-root-remote.sh + .yaml)
- Unit tests: 8/8 PASS
- Coverage: 9 paths × 6 fields = 54 cells, all 100%
- GaC gate: 84/86 (2 pre-existing FAILs not introduced by this PR)

## related

- 父设计: `docs/OMOSTATION-FORWARD-PLAN-v2.md`
- 根因分析: `.omo/_knowledge/design/root-cause-analysis-2026-09-25.md` (#4312)
- 关联 BET: BET-Y2Q4-SH-1 (P0 L2.5 self-healing layer, done via #4316/#4322)
- 关联 BET: BET-Y2Q4-SH-3 (P1 gitlink/launchd/asset consistency)
- 关联 BET: BET-Y2Q4-SH-4 (P1 multi-registry alias resolver)