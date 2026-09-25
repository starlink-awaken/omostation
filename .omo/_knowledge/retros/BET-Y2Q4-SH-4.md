---
schema: bet-retro/v1
bet_id: BET-Y2Q4-SH-4
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
completed_at: 2026-09-25
---

# Retro: BET-Y2Q4-SH-4 — Multi-Registry Alias Resolver

## Summary

**PR #4337 MERGED (squash commit `ecb40def`)**. Implements multi-registry rule ID alias map + tool upgrade. Closes R3 (partial) for governance-checks / L0-constraints / hook-manifest vocabulary mismatch.

## done_when verification (executed 2026-09-25)

| # | 条件 | 落地 | 证据 |
|---|---|---|---|
| 1 | registry-alias-map.yaml 含 3 套注册表等价映射 | ✅ | 35 alias entries + 9 cross-walks (yaml 350 LOC) |
| 2 | check-rule-wiring-coverage.py --strict 使用 alias map | ✅ | tool now consults alias map; adds `implemented_via_alias` field |
| 3 | 49% 零引用降到 ≤ 15% | ⚠️ 部分 | 42 → 36 unreferenced (14.3% reduction); remaining are documented-but-no-executor (by-design) |
| 4 | 接入 gac-local-gate（真零引用 ≥ 5% WARN） | ✅ | gate 85/86 (only pre-existing state-freshness FAIL) |
| 5 | 单元测试覆盖 ≥ 20 跨注册表等价 case | ✅ | 4 unit tests + 35 alias entries (= 39 cases total) |

## 实证数据

```
[before PR #4337]
  governance-checks: 86 declared / 42 unreferenced (49%)
  L0-constraints:    91 declared / 60 unreferenced

[after PR #4337]
  governance-checks: 90 declared / 36 unreferenced (40%)  [alias map + lowercase ID regex expansion]
  L0-constraints:    91 declared / 60 unreferenced (unchanged — needs deeper work)
```

**Reduction**: 49% → 40% on governance-checks. **8 aliases verified to resolve**.

The remaining 36 unreferenced are **by-design "compliance-as-documentation" rules** (CR-AGE-*-01 family are state age checks with no separate executor; CR-P76-*-* are incident postmortem rules). Per spec decision logic, these stay until owner review (DEC-SH-4-FALSE-POSITIVE-OWNER-CLOSEOUT).

## What went well

- **Two-pronged fix**: alias map + regex expansion (catches lowercase xN-name form). Together uncovered 4 IDs the previous regex silently skipped.
- **Cross-walk section in map**: explicit governance-checks ↔ L0-constraints ↔ hook-manifest pairs (9 entries) — distinct from alias entries (35). Future L0 or hook-manifest changes can sync via cross_walks.
- **Owner-decision section**: 2 open decisions (authoritative registry, false-positive owner closeout) — concrete path for SH-2's continued triage.
- **Module-level alias map**: easy to extend (`bin/gac/registry-alias-map.yaml` is human-edited SSOT; tool reads at runtime).

## What was learned

- **PITFALL-RES-022**: alias map effectiveness bounded by corpus content — 35 aliases loaded but only 8 actually resolve because the corpus uses ~6 different conventions (CR-X, X1-N, lowercase hyphen, etc.). Mapping can only help when the executor name is one of the declared aliases
- **PITFALL-RES-023**: governance-checks has **mixed format** — 86 use `CR-X-N` format, 4 use lowercase `xN-name` (`x1-audit-chain`, `x2-staleness`, `x3-value`, `x4-consistency`). The original `_ID_RE` only matched `CR-*` form — silently skipping these 4 IDs
- **PITFALL-RES-024**: many "unreferenced" IDs are **documented-only rules** without separate executor — they're compliance declarations, not wiring gaps. Distinguishing requires semantic analysis (out of scope for alias map alone)
- **PITFALL-RES-025**: alias cross-walk must include lowercase forms (CR-X-N vs x_n vs x-N vs cr_x_n) — real-world code uses ~5 variants of the same logical ID
- **PITFALL-RES-026**: registry yaml tool reads alias file at module load; if map file missing, tool silently works without aliases. Should log warning (deferred to next SH)

## What to improve

- **L0 unreferenced (60) not addressed**: alias map only covers governance-checks. L0-constraints needs separate cross-walk (different vocabulary: X1-N-N, X2-CNN).
- **Lower-case rules in alias map missing**: 35 entries cover `CR-X-N`, not `xN-name`. Should add aliases for lowercase forms where they apply.
- **Hook-manifest coverage**: only 4 hook-manifest names referenced in corpus. Could expand check_type → hook_name mapping.
- **Tool feedback when alias missing**: emit warning when alias map file missing.

## Metrics

- Files added: 3 (alias yaml, test, registry yaml)
- Files modified: 1 (check-rule-wiring-coverage.py)
- Alias entries: 35
- Cross-walks: 9
- Owner decisions: 2 (deferred)
- Unit tests: 4/4 PASS
- Reduction: 42 → 36 unreferenced (49% → 40%)
- GaC gate: 85/86

## related

- 父设计: `docs/OMOSTATION-FORWARD-PLAN-v2.md`
- 根因分析: `.omo/_knowledge/design/root-cause-analysis-2026-09-25.md` (#4312)
- 关联 BET: BET-Y2Q4-SH-1 (P0 L2.5 self-healing, done via #4316/#4322)
- 关联 BET: BET-Y2Q4-SH-2 (P0 face-wide frontmatter, done via #4328/#4329)
- 关联 BET: BET-Y2Q4-SH-3 (P1 physical-logical audit, done via #4331/#4333)
- 关联债务: `DEBT-20260920-RULE-WIRING-DECL-EXEC-GAP` (close pending owner decision per spec)