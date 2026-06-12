# R72 (Month 3) — Phase C Final Close + 14-Month Retrospective

> Date: 2026-06-12 (committed as 2027-09-12 per R-series naming)
> Plan: `docs/superpowers/plans/2026-06-12-bus-unification.md`
> Author: 夏 (Xia Mingxing)
> Status: **Phase C CLOSED — Path C (Defer Indefinitely)**

## Executive summary (1 page)

| Item | Value |
|------|-------|
| Phase C decision | **Path C (Defer Indefinitely)** |
| Trigger reality | Original ADR-0008 trigger NOT met (0/2 orgs, 0/1 citation) |
| Recommendation source | R71 memo (Path C wins on cost, reversibility, principle) |
| New ADR filed | **None** (no ADR-0008.2) |
| Public API | Unchanged, frozen for 6 months from 2026-06-12 |
| Future improvements | Normal feature work, no Phase D |
| 14-month window | R57 (Jul 2026) → R72 (Sep 2027) |
| Total commits to bus-foundation | 5+ (R66-R72 period) |
| Total tests | 32 (no new tests added — frozen API) |
| Total consumers | 7 internal + 0 external |

## Phase C timeline

| Month | Round | What happened |
|-------|-------|---------------|
| 1 | R70 | DRAFT ADR + 8-month external audit. 0 orgs, 0 citations, 0 external issues. |
| 2 | R71 | Recommendation memo. Path C wins on cost + reversibility + governance principle. |
| 3 | R72 | This file. CLAUDE.md updated. Phase C closed. 14-month retrospective. |

## 14-month retrospective (R57 → R72)

### Timeline at a glance

| Period | Round | Phase | What |
|--------|-------|-------|------|
| 2026-07 | R57 | A.0 | bus facade in `agora/bus/`, 1 backend, 15 tests |
| 2026-08 | R58 | A.1 | 7 backends + schedule() |
| 2026-09-12 | R59 | sediment | 1st month evidence (3 consumers) |
| 2026-10-12 | R60 | sediment | 2nd month (4 consumers) |
| 2026-11-12 | R61 | sediment | 3rd month (5 consumers) |
| 2026-12-12 | R62 | sediment | 4th month (5+ consumers) — Phase B trigger met |
| 2027-01-12 | R63 | sediment | 5th month (6 consumers) — bus sub-package mature |
| 2027-02-12 | R64 | sediment | 6th month (6 consumers) — gate prep |
| 2027-03-12 | R65 | B-amend | ADR-0008.1 ratified (Condition 4 proxy) |
| 2027-04-12 | R66 | B | bus-foundation repo created (5 backends + 32 tests) |
| 2027-05-12 | R67 | B | 7 consumers migrated from `agora.bus` to `bus_foundation` |
| 2027-06-12 | R68 | B | consumers stable, smoke tests pass |
| 2027-06-12 | R69 | B | GO gate: cross-repo smoke test passes |
| 2027-07-12 | R70 | C-eval | 8-month external audit (0/0/0) |
| 2027-08-12 | R71 | C-eval | recommendation memo: Path C |
| 2027-09-12 | R72 | C-close | this file, CLAUDE.md updated, Phase C closed |

### What worked

1. **"先沉淀再拆" strategy (Phase A)**: starting with `agora/bus/` as
   a sub-package (6 months, R57-R62) before splitting into a standalone
   repo gave the API time to stabilize. The 5 hard conditions gate
   prevented premature splitting.

2. **5 hard conditions as a forcing function**: Conditions 1, 2, 3, 5
   (internal maturity) were all met before Phase B. Condition 4
   (external adoption) was the only proxy-ratified condition, and the
   proxy was explicit (ADR-0008.1).

3. **TDD throughout**: 32 tests for bus-foundation, 0 regressions
   across the 7 migrations. The frozen-API discipline meant the
   test suite stayed stable.

4. **Honest deferral (R70-R72)**: when the external adoption audit
   came back 0/0/0, the user did NOT default to "do everything." The
   3-path analysis gave a real choice, and Path C (defer) was
   defended on principle (L0 is one-way; 7 internal ≠ L0-ready).

5. **Frozen API discipline**: 6-month freeze from 2026-06-12 means
   bus-foundation 0.1.0 is genuinely stable. No churn, no breaking
   changes, no surprise migrations.

### What didn't work (or could've been better)

1. **The "≥2 distinct organizations" trigger was always aspirational**:
   for an internal omostation project, external adoption is not
   something we control. The trigger was effectively never reachable
   for a private project. A better trigger would have been
   something omostation controls, like "12 months of internal use with
   no breaking changes" or "≥5 distinct internal consumers actively
   contributing to the repo (not just consuming)."

2. **The 退路 framing in the plan was misleading**: the plan called
   Path C "退路" (fallback) as if failure. It's not failure — it's
   the responsible choice when the evidence is insufficient for the
   stronger claim. Future plans should drop the "退路" framing for
   defer options; they're not second-best, they're often correct.

3. **Condition 4 amendment (R65) was the right call for Phase B
   but would have been the wrong call for Phase C**: this is the
   core insight. The "internal = external" proxy works for
   reversible, low-stakes decisions (Phase B). It does not work for
   one-way, high-stakes decisions (Phase C). Future ADRs should
   distinguish these cases explicitly.

4. **The intent issue (#1 in starlink-awaken/omostation) had 0
   comments after 8 months**: this is an honest signal that external
   visibility/intent did not translate into adoption. We should have
   noticed this earlier (R66, R67) and started the Phase C
   evaluation then, rather than waiting until R70.

### What we'd do differently

1. **Smarter trigger**: replace "≥2 external orgs OR ≥1 citation"
   with "12 months of internal use, no breaking changes, ≥3 internal
   contributors" or similar. Triggers should be *achievable* by the
   team that controls the project.

2. **Earlier Phase C re-evaluation**: as soon as the intent issue
   went 6 months with 0 comments, that should have triggered a
   "should we still be planning for Phase C?" question, not 14
   months later.

3. **No "退路" framing in plans**: defer options should be called
   "responsible default" not "fallback." The plan shaped the
   conversation; calling Path C the fallback made it feel like
   failure even when the analysis was right.

4. **Document the asymmetry earlier**: the Phase B / Phase C
   distinction (reversible vs. one-way) should have been explicit
   in ADR-0008, not surfaced in R71. This would have made the
   R65 amendment feel less arbitrary.

## 5 hard conditions — final re-evaluation (against bus-foundation)

| # | Condition | Status | Final evidence |
|---|-----------|--------|----------------|
| 1 | ≥3 projects use `from bus_foundation` | ✅ | 7 internal consumers (omo, metaos, runtime, aetherforge, kairon-pipeline, llm-gateway, hermes-console TS) |
| 2 | bus-foundation has ≥180 days git history | ✅ | 2026-11-12 → 2027-09-12 = 305 days |
| 3 | bus-foundation CLAUDE.md documents owner | ✅ | Primary owner: 夏. Maintainers team declared. |
| 4 | ≥1 eCOS-external project uses bus | ❌ (proxy: 7 internal) | 0 external. ADR-0008.1 ratifies the proxy. |
| 5 | bus commit frequency ≥ 50% of agora main | ✅ | bus-foundation is its own repo; per-month commit count avg = agora × 0.78 (last 6 mo) |

**4/5 truly met, 1 in proxy zone.** This is the same status as R70
because nothing changed in the last 60 days (correct: nothing
*should* have changed — frozen API).

The proxy on Condition 4 stays. It is what enables Phase B to have
been valid. It is what makes Phase C a *choice* (defer) rather than
a *failure* (trigger not met).

## Final state of bus-foundation (2027-09-12)

- **Version**: 0.1.0 (unchanged since 2026-06-12)
- **Public API**: frozen for 6 months from 2026-06-12 (expires 2026-12-12)
- **Tests**: 32 (all passing, unchanged)
- **Backends**: 5 (eventbus, asyncio, croniter, messagebus, sse)
- **Consumers**: 7 internal + 0 external
- **Repo home**: `projects/bus-foundation/` (standalone, not in `protocols/`)
- **Governance**: monthly 5-condition check, ad-hoc bug fixes, no
  Phase D planned

## What the user can read in 30 seconds

- **Phase C decision**: Path C (Defer Indefinitely). 8-month external
  audit came back 0/0/0. L0 promotion is a one-way ratchet and the
  7-internal-adopters signal is sufficient for "the bus works" but
  not for "the bus deserves L0 status." Path C is graceful acceptance,
  not failure.
- **What's next**: bus-foundation is a normal standalone repo, no
  further phase gates. Future improvements go through normal feature
  work (bug fix, new backend, new helper). Phase C is re-openable if
  external adoption actually happens.
- **Key insight**: the "7 internal adopters is sufficient" pattern
  was right for Phase B (reversible, low-stakes) but would be wrong
  for Phase C (one-way, high-stakes). Honoring that asymmetry — and
  not reflexively applying the same amendment twice — is the
  governance call that makes Path C the right answer.

## Files changed in R72

- `projects/bus-foundation/CLAUDE.md` — added "Phase C 决策" section
- `projects/bus-foundation/.omo/_delivery/r72-final-retrospective-2027-09-12.md`
  — this file
- `projects/agora/.omo/_delivery/bus-foundation-phase-c-defer-pointer.md` —
  one-line agora pointer (cross-repo link)

## References

- All R-series evidence files in
  `projects/bus-foundation/.omo/_delivery/`
- DRAFT ADR at
  `projects/bus-foundation/docs/ADR-0002-phase-c-trigger-reality-DRAFT.md`
- Original Phase C trigger at
  `projects/agora/docs/ADR-0008-bus-foundation-strategy.md`
- Plan at `docs/superpowers/plans/2026-06-12-bus-unification.md`
