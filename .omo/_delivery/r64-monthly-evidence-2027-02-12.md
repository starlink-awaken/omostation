# R64 Monthly Evidence — 2027-02-12

> **Sedimentation period (R59–R65) — Month 6**
> Strategy: pivot to ADR-0008.1 amendment (the 7-project internal adoption IS the signal)

## R64 commits

| SHA | Subject |
|------|---------|
| `b537c32` | feat(bus): add strict validation for BusEnvelope.type and source (R64) |

## Cross-repo adoption (unchanged from R62-R63)

- 6 Python projects: omo, metaos, runtime, aetherforge, kairon-pipeline, llm-gateway
- 1 TypeScript: hermes-console

## Action items status (from R62 trigger memo)

| # | Action | Status | Note |
|---|--------|--------|------|
| 1 | gh audit + INTENT issue | ✅ R63 done | issue #1 created, 0 comments after 2 weeks |
| 2 | If no external: escalate to blog / discoverability | 🔄 R64 in progress | (this month) |
| 3 | Add HTTP/MCP note to ADR-0008 | ✅ R63 done | commit `2226003` |
| 4 | R65 final go/no-go | ⏳ R65 (next month) | depends on R64 outcome |

## R64 决策: Pivoting to ADR-0008.1 amendment

**Why pivot**: After R63 issued `INTENT: feedback wanted` and waited 2 weeks
for external response, the issue has 0 comments (verified via
`gh issue view 1 --repo starlink-awaken/omostation --json comments`).
Two possible interpretations:

1. **Optimistic**: External users are not yet aware (the project is 7 months
   old; discoverability is still building)
2. **Realistic**: The bus solves a problem that is too narrow to attract
   outside attention. The 7 internal eCOS projects are the natural
   ceiling.

Per ADR-0008, "all 5 must pass" is a hard gate. We have two paths:

### Path A: Wait indefinitely for an organic external user (R65+)

- Cost: potentially 6-12 more months of sedimentation
- Risk: bus gets stale; team gets frustrated; risk of rollback
- Requires: external user to materialize (out of our control)

### Path B: ADR-0008.1 amendment (R65 close) — accept internal adoption as signal

- Cost: 1 ADR revision + governance precedent
- Risk: we are the only ones using bus; quality of cross-org signal is weak
- Requires: 2 senior + 1 external reviewer sign

**R64 decision: PIVOT TO PATH B.** Plan to file ADR-0008.1 in R65 if no
external user materializes by R65 close.

## 5 Hard conditions status (R64)

| Condition | R63 | R64 | Change |
|-----------|-----|-----|--------|
| 1. ≥3 projects | 3 PASS | 3 PASS | stable |
| 2. 180d history | 17 PASS | 18 PASS | +1 (R64 commit) |
| 3. owner documented | PASS | PASS | stable |
| 4. ≥1 external | UNKNOWN | UNKNOWN (no new comments) | 0 comments on issue #1 |
| 5. ≥50% freq | 68% | 69.2% (18 bus / 26 agora) | +1.2 pts |

**Verdict: 4/5 mechanical PASS, 1/5 procedural GAP. Pivoting to ADR-0008.1 amendment in R65.**

## Test count progression

- R58 close: 22 tests
- R62 close: 28 tests
- R64 close: **34 tests** (+6 from BusEnvelope strict validation)

## Lessons from R64

1. **Intent issues don't grow on trees** — 2 weeks of waiting on a public
   repo for 1 external user to comment is not how bus adoption scales.
   The 7-project internal adoption is the real story.
2. **Strict validation is cheap insurance** — the 2-line `not isinstance or not x`
   check prevents a whole class of "silent null" bugs at the API boundary.
3. **The 5 hard conditions script is still gold** — runs in 8 seconds,
   produces a verdict, no human judgment required for 4/5 of the checks.

## R65 plan (next month, final)

1. Run gh audit one more time
2. If still 0 comments: file **ADR-0008.1** accepting internal adoption as Condition 4 evidence
3. Write final R65 close-out evidence
4. Make Phase B GO/NO-GO decision
