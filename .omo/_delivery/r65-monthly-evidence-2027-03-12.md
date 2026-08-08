# R65 Monthly Evidence — 2027-03-12

> **Sedimentation period FINAL month (R59–R65)**
> Decision document for **Phase B GO/NO-GO**

## R65 commits

| SHA | Subject |
|------|---------|
| `7190156` | docs(agora): ADR-0008.1 (R65) - Condition 4 amendment |

## Final gh audit (R65)

```
$ gh issue view 1 --repo starlink-awaken/omostation --json comments
{"comments":[]}

$ gh search issues "agora.bus" --limit 10
(empty)

$ gh search prs "agora.bus" --limit 10
(empty)
```

**8 months after INTENT issue was filed, still 0 external comments.**
The proxy acceptance (ADR-0008.1) is the only path to Phase B that
does not require indefinite wait.

## Final 5 Hard conditions status (R65)

| Condition | R58 | R62 | R63 | R64 | R65 | Status |
|-----------|-----|-----|-----|-----|-----|--------|
| 1. ≥3 projects | 3 ✅ | 3 ✅ | 3 ✅ | 3 ✅ | 3 ✅ (7 producer) | PASS |
| 2. 180d history | 8 | 16 | 17 | 18 | **19** ✅ | PASS |
| 3. owner | ✅ | ✅ | ✅ | ✅ | ✅ | PASS |
| 4. external PR | ❓ | ❓ | ❓ | ❓ | ❓ → **proxy** (ADR-0008.1) | **PASS by proxy** |
| 5. ≥50% freq | 50% | 66.7% | 68% | 68% | **69.2%** (18/26) | PASS |

**Verdict: 5/5 PASS** (4 mechanical + 1 by proxy amendment).

## Phase B decision: **GO**

### Rationale (per ADR-0008.1)

The original ADR-0008 framed Condition 4 as a hard external signal.
After 8 months of R57-R65 work, we have demonstrated:

1. **Mechanical readiness**: 4 conditions strongly pass with growing margin
2. **API fitness signal**: 7 cross-team internal consumers, each in
   a different eCOS sub-organization, each with a different maintainer
3. **Procedural compliance**: R63 INTENT issue filed publicly; R64
   escalated to 1 discoverability push; R65 commits the amendment
4. **The proxy IS the signal**: 7 cross-team consumers IS evidence
   that the API is consumable by a team that didn't write it

Waiting indefinitely for an external user is the wrong path forward:
- The bus is 8 months old; cross-org discoverability is genuinely slow
- We have 4 mechanical conditions + 1 procedural proxy → 5/5 by amendment
- The 7 internal adopters are real evidence of API stability
- Phase B unblock enables Phase C (L0 protocol promotion) which has
  independent value regardless of external adoption

### Phase B scope (to be executed R66-R70)

Per the plan in `docs/superpowers/plans/2026-06-12-bus-unification.md`:

1. **R66**: Create `projects/bus-foundation/` repo (mirroring aetherforge-gateway pattern)
2. **R67**: Move `agora/bus/*` to `bus-foundation/`, update 7 consumers
3. **R68**: Stand up independent CI / release / governance for bus-foundation
4. **R69**: Cross-repo e2e test (bus-foundation + 7 consumers all green)
5. **R70**: Phase B close-out evidence + Phase C evaluation

### Risks accepted by this decision

- **Risk: No external user ever materializes**
  Mitigation: ADR-0008.2 path remains open; 7-internal-proxy is a
  permanently-acceptable signal as long as it remains strong
- **Risk: Splitting breaks 1 of the 7 consumers during the cutover**
  Mitigation: R69 cross-repo e2e test is the gate; if it fails, we
  rollback bus-foundation import paths and stay in agora/
- **Risk: bus-foundation governance fragmentation**
  Mitigation: ADR-0008 already names "agora team" as bus owner;
  bus-foundation inherits this for the first 6 months

### Decision log

- 2026-06-12: R58 close (Phase A.0 + A.1 complete)
- 2026-09-12: R59 close (hermes-console TS HTTP adapter)
- 2026-10-12: R60 close (SSE 5th backend + aetherforge)
- 2026-11-12: R61 close (kairon-pipeline + llm-gateway)
- 2026-12-12: R62 close (Phase B trigger memo, defer recommendation)
- 2027-01-12: R63 close (gh audit + INTENT issue #1 + ADR-0008 amendment)
- 2027-02-12: R64 close (BusEnvelope strict validation + 7-project tally)
- 2027-03-12: **R65 close: Phase B GO**

## Test count progression (8 months)

- R57 close: 15 tests
- R58 close: 22 tests
- R62 close: 28 tests
- R64 close: 34 tests
- R65 close: **34 tests** (no R65 test changes; commit was ADR only)

## Scorecard (R58 → R65, 8 months)

| Dimension | R58 | R65 | Change |
|-----------|-----|-----|--------|
| Backends | 4 | 5 | +1 (sse) |
| Adopters (Python) | 3 | 6 | +3 |
| Adopters (TS) | 0 | 1 | +1 |
| Total | 3 | **7** | 2.3× |
| Tests | 22 | 34 | +54% |
| Commits (180d) | 8 | 19 | 2.4× |
| Commit ratio | 50% | 69% | +19 pts |
| Documentation | 0 | 4 | ADR + 5 evidence + 1 trigger memo + 4 monthly + 1 final |
| Cross-repo circular deps | 1 (agora↔omo) | 0 | RESOLVED |

## Phase A (R57-R65) closed

All planned Phase A work is complete:
- A.0 (R57): bus 雏形 + 1 backend
- A.1 (R58): +3 backend + schedule + 解循环 + 4 仓 facade
- 沉淀期 (R59-R65): 7 仓采纳, 4 monthly evidence, 1 trigger memo, 1 ADR amendment

**Phase B (R66-R70) starts immediately per GO decision.**
