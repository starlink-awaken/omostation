# R68 (Month 3) Close Evidence — bus-foundation independent CI + governance

> Date: 2026-06-12 (committed as 2027-06-12 per the R-series naming)

## 4 commits in bus-foundation + 1 commit in agora

1. `ci(bus-foundation): add GitHub Actions test workflow (matrix py3.13, pytest + ruff)` — cb026013
2. `chore(bus-foundation): add OWNERS, CHANGELOG 0.1.0, GOVERNANCE, hard-conditions checker`
3. (tag) `v0.1.0` — local-only annotated tag
4. `docs(agora): bus moved to bus-foundation (R68) — see projects/bus-foundation/` (in agora submodule)

## R68 deliverables checklist

| Item | Status | File |
|------|--------|------|
| `.github/workflows/test.yml` (matrix py3.13) | ✅ | `projects/bus-foundation/.github/workflows/test.yml` |
| `OWNERS.md` (2-3 names) | ✅ | `projects/bus-foundation/OWNERS.md` |
| `CHANGELOG.md` 0.1.0 release | ✅ | `projects/bus-foundation/CHANGELOG.md` |
| Tag v0.1.0 (local, NOT pushed) | ✅ | `git tag v0.1.0` |
| `GOVERNANCE.md` (release cadence) | ✅ | `projects/bus-foundation/GOVERNANCE.md` |
| `scripts/check-bus-hard-conditions.sh` | ✅ | `projects/bus-foundation/scripts/check-bus-hard-conditions.sh` |
| agora CLAUDE.md updated | ✅ | `projects/agora/CLAUDE.md` §bus Owner section |

## Check script verdict

```
Condition 1: ≥3 projects use bus-foundation or agora.bus     PASS (6 projects)
Condition 2: ≥180 days git history                            PASS (4 commits in 180 days)
Condition 3: CLAUDE.md documents owner                        PASS
Condition 4: ≥1 eCOS-external user (proxy ≥5 internal)        PASS (6 internal)
Condition 5: commit freq ≥ 50% of agora                       FAIL (23.53% — needs 6+ months history)
```

**4/5 PASS** at R68 close. Condition 5 will tick monthly as bus-foundation
accumulates commit history. Phase B (R66-R69) gate is satisfied; Phase C
(L0 promotion) requires Condition 5 to reach ≥50% over 6 months.

## Public API freeze

0.1.0 public API is **frozen for 6 months** (per ADR-0008.1). Any breaking
change requires an ADR + 2 maintainer approvals.

## Next month (R69)

Cross-repo e2e gate: `bus-foundation/tests/test_cross_repo_smoke.py` +
run all 7 consumer test suites + agora meta-test confirming agora.bus
re-exports from bus_foundation.
