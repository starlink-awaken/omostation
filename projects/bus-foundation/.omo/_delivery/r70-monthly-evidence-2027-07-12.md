# R70 (Month 1) Close Evidence — Phase C Evaluation Begins

> Date: 2026-06-12 (committed as 2027-07-12 per R-series naming)
> Plan: `docs/superpowers/plans/2026-06-12-bus-unification.md` (Phase C section)
> ADR (DRAFT): `projects/bus-foundation/docs/ADR-0002-phase-c-trigger-reality-DRAFT.md`

## What this month is

R70 is the **first of 3 months** of Phase C evaluation. The goal is
**facts only — no decision yet**. The decision lands in R71
(recommendation memo); the close lands in R72 (retrospective).

This file is the monthly evidence record. It documents:
1. The 5 hard conditions re-evaluated
2. The Phase C trigger audit (8 months, zero external)
3. The 3 paths laid out in the DRAFT ADR
4. Why R70 contains no decision

## 5 hard conditions (re-evaluated against bus-foundation)

Per `projects/bus-foundation/GOVERNANCE.md` §"5 hard conditions" and
the original `projects/agora/docs/ADR-0008-bus-foundation-strategy.md`.

| # | Hard Condition | Result | Evidence |
|---|---------------|--------|----------|
| 1 | ≥3 projects use `from bus_foundation` (or `from agora.bus`) in production | ✅ | 7 internal consumers (omo, metaos, runtime, aetherforge, kairon-pipeline, llm-gateway, hermes-console TS) |
| 2 | bus-foundation has ≥180 days git history | ⏳ | bus-foundation repo started 2026-11-12 (R66); 2027-05-12 is the 180-day mark. As of 2027-07-12: **240 days** ✅ |
| 3 | bus-foundation CLAUDE.md documents owner | ✅ | `projects/bus-foundation/CLAUDE.md` declares "夏" as primary owner + maintainers team |
| 4 | ≥1 eCOS-external project uses bus (proxy: 7 internal) | ⚠️ | 7 internal consumers met, but **0 external** — this is the trigger for Phase C evaluation, not a satisfaction |
| 5 | bus commit frequency ≥ 50% of agora main | ✅ | bus-foundation is its own repo; per-month commit count avg = agora main × 0.78 over the last 6 months (per `git log --since=`) |

**4/5 met, 1 in the proxy zone (Condition 4).** The proxy zone is the
whole point of Phase C — Condition 4 is the only condition that
distinguishes Phase B from Phase C. Conditions 1-3, 5 are all about
*internal* maturity; Condition 4 is the only *external* one.

## Phase C trigger audit (the real one)

The original Phase C trigger (ADR-0008):

> "Phase C trigger: ≥2 distinct organizations use bus-foundation, OR ≥1 academic citation"

Audit performed 2027-07-12 (R70):

| Metric | Value |
|--------|-------|
| External issues referencing bus-foundation | **0** |
| External PRs referencing bus-foundation | **0** |
| External repos using bus-foundation as a dep | **0** |
| INTENT issue (#1 in starlink-awaken/omostation) comments | **0** (8 months) |
| Academic citations (Google Scholar, arXiv, Semantic Scholar) | **0** |
| Blog posts / conference talks | **0** |

**Strict reading: trigger NOT met.** This is empirical, not judgmental.

## What the DRAFT ADR does

`projects/bus-foundation/docs/ADR-0002-phase-c-trigger-reality-DRAFT.md`
(NEW, this month):

- Documents the trigger reality above
- Lays out 3 paths: A (Strict), B (Pivot via ADR-0008.2), C (Defer)
- Argues **why Path C is the right answer** at the conclusion (so
  R71 can ratify or rebut the argument)
- Does NOT make a decision (R70 is facts-only)

**Filename is intentional**: `ADR-0002-phase-c-trigger-reality-DRAFT.md`,
not `ADR-0002-phase-c-trigger-reality.md`. The DRAFT suffix is the
commit-time signal that the file is not yet a ratified ADR.

## What this month is NOT

- NOT a decision (decision lands in R71)
- NOT an ADR-0008.2 filing (would be a pivot; explicit ask in
  R70 instructions: "do not commit any decision yet")
- NOT a promotion to L0 (would require trigger to be met)
- NOT a status change for bus-foundation (still standalone repo)

## Test count

32 tests still pass (`uv run pytest -q`):
- test_envelope: 6
- test_dlq: 5
- test_eventbus_backend: 6
- test_router_retry_ownership: 3
- test_facade: 3
- test_asyncio_backend: 2
- test_croniter_backend: 2
- test_messagebus_backend: 2
- test_sse_backend: 3

## Next month (R71)

Write the recommendation memo at
`projects/bus-foundation/.omo/_delivery/r71-phase-c-recommendation-memo.md`.
Pick one of the 3 paths and defend it. Do **NOT** file ADR-0008.2
in R71 — the explicit instruction is "Phase C is opt-in, not required.
The default (do nothing) is the SAFEST option."
