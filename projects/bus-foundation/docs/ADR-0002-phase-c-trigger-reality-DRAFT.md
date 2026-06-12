# ADR-0002: Phase C Trigger Reality — 8-Month Audit (DRAFT, not yet ratified)

> **Status**: DRAFT (R70)
> **Date**: 2026-06-12 (committed as 2027-07-12 per R-series naming)
> **Author**: 夏 (Xia Mingxing)
> **Deciders**: pending (this month is facts-only, no decision)
> **Supersedes**: none
> **Related**: `projects/agora/docs/ADR-0008-bus-foundation-strategy.md` (original Phase C trigger)
> **Related**: `docs/ADR-0008.1-condition4-proxy.md` (R65 amendment for Phase B)

---

## Context

ADR-0008 (R57) defined the **Phase C trigger** as:

> "Promote bus-foundation to L0 protocol layer at `protocols/bus-foundation/`. Trigger: ≥2 distinct organizations use bus-foundation, OR ≥1 academic citation."

Phase B (R66-R69) is complete: bus-foundation is now a standalone repo at
`projects/bus-foundation/`, with 7 internal consumers migrated. R65 ratified
ADR-0008.1 (Condition 4 proxy) to allow Phase B to proceed despite zero
external adopters.

R70 begins Phase C evaluation. This ADR is **DRAFT** — it documents the
trigger reality and lays out 3 paths for evaluation. The actual decision
(which path to take) lands in R71.

---

## The Trigger Reality (8-Month Audit)

Period: 2026-11-12 → 2027-07-12 (8 months, the lifetime of bus-foundation as
a documented concept in ADR-0008).

### External Adoption Metrics (all zero)

| Metric | Value | Source |
|--------|-------|--------|
| External issues referencing bus-foundation | 0 | GitHub issues search |
| External PRs referencing bus-foundation | 0 | GitHub PRs search |
| External repos using bus-foundation as a dep | 0 | GitHub search `dependency:bus-foundation` |
| INTENT issue (#1, starlink-awaken/omostation) | 0 comments after 8 months | GitHub issue view |
| Academic citations | 0 | Google Scholar, arXiv, Semantic Scholar |
| Blog posts / conference talks | 0 | web search |

### Internal Adoption Metrics (7 consumers, all real)

| Consumer | Status | Migrated in |
|----------|--------|-------------|
| omo | migrated (R67) | 2026-06-12 |
| metaos | migrated (R67) | 2026-06-12 |
| runtime | migrated (R67) | 2026-06-12 |
| aetherforge | migrated (R67) | 2026-06-12 |
| kairon-pipeline | migrated (R67) | 2026-06-12 |
| llm-gateway | migrated (R67) | 2026-06-12 |
| hermes-console (TS) | JSON SSE wire-format consumer | n/a (always) |

7 internal consumers = 0 external consumers. The asymmetry is real.

### Verdict on the ORIGINAL Trigger

Strictly read, **the original ADR-0008 Phase C trigger is NOT met**:
- "≥2 distinct organizations use bus-foundation" → 0 organizations
- "≥1 academic citation" → 0 citations

This is an empirical fact, not a judgment. The plan said
"不达标退路: R70 不达标 → 继续 Phase B, R78 再评" — but the 退路 was
written assuming Phase B, not the post-Phase-B state. R70 is a new
evaluation point that didn't exist when ADR-0008 was written.

---

## 3 Paths for Phase C

### Path A — Strict (Wait Indefinitely for External Adoption)

- **Action**: do not promote to L0; re-evaluate every 6 months
- **Pros**: faithfully honors ADR-0008's original trigger; zero governance risk
- **Cons**: may never happen; L0 status is forever out of reach if omostation
  is the only community using bus-foundation
- **Cost of action**: ~0
- **Cost of inaction**: misses a "this is stable enough to be L0" signal
  if the 7 internal adopters are actually sufficient evidence
- **When to choose**: if the user strongly believes Phase C must require
  external adoption, and 7 internal adopters are not sufficient

### Path B — Pivot (Ratify ADR-0008.2: 7 Internal Adopters = Phase C Proxy)

- **Action**: file a new ADR (ADR-0008.2) that ratifies 7 internal adopters
  as sufficient for Phase C, mirroring the R65 amendment for Phase B
- **Pros**: consistent with the R65 precedent; honors empirical reality
  (the bus works in 7 places); allows Phase C to proceed
- **Cons**: this is a **second** time we're amending the original trigger.
  The pattern is "lower the bar, ratify, proceed" — governance smell.
  Phase B and Phase C would both have been triggered by internal
  adoption, which means ADR-0008's "external adoption" requirement has
  been bypassed twice. Anyone reading ADR-0008 in the future will see
  the original bar and wonder why we ignored it.
- **Cost of action**: medium (need to write ADR-0008.2, defend in review,
  accept the governance smell)
- **Cost of inaction**: stays in the safer Path C territory
- **When to choose**: if 7 internal adopters is actually strong evidence
  that the bus is L0-ready, and we want to be consistent with R65

### Path C — Defer Indefinitely (The 退路 / Fallback)

- **Action**: do not promote to L0. bus-foundation stays as a standalone
  repo. Future improvements go through normal feature work, not a
  Phase D. Document the decision in `CLAUDE.md`.
- **Pros**:
  - The bus is already stable. 7 internal consumers is real evidence
    the bus *works* — but the question for Phase C is not "does the bus
    work?" (yes, it does), it is "does the bus deserve L0 protocol
    layer status?" — and that's a *governance* claim, not an API
    fitness claim.
  - L0 status is a one-way ratchet. Once promoted, the bus joins the
    protocol-layer governance and inherits constraints we don't
    currently need. Premature commitment.
  - Default (do nothing) is the safest governance option. We are not
    forced to act.
  - Phase C is opt-in, not required. ADR-0008 says "R70 不达标 → 继续
    Phase B, R78 再评" — Path C is the most conservative read of that
    line.
- **Cons**:
  - "退路" framing in the original plan implies this is failure. It
    is not — it is the responsible choice.
  - Anyone who reads the plan and expects Phase C to be a
    "promotion" event will be surprised.
- **Cost of action**: ~0 (one CLAUDE.md update + one retrospective)
- **Cost of inaction**: ~0 (bus continues to work as a standalone repo)
- **When to choose**: when the 7-internal-adopters signal is *real but
  not enough* — and "enough" is a governance call, not a popularity
  contest.

---

## Important Distinction: Phase B vs Phase C

The "7 internal adopters is sufficient" pattern was used once (R65 for
Phase B). The honest question for Phase C is: does the same logic apply?

| Dimension | Phase B (R65 amendment) | Phase C (R70 evaluation) |
|-----------|------------------------|--------------------------|
| Question | "should the bus be a standalone repo?" | "should the bus be promoted to L0?" |
| Evidence type | API fitness (does the bus work in 7 places?) | Governance claim (does the bus *deserve* L0 status?) |
| Cost of being wrong | low (it's a folder, easy to reverse) | high (L0 is one-way; you can't un-promote) |
| Reversibility | easy (merge back) | hard (would need to re-ADR L0 removal) |

**Key insight**: Phase B's "7 internal adopters" argument was about API
fitness. The 7 adopters say "the bus works" — which is a *technical*
claim with high confidence. Phase C's "7 internal adopters" argument
would be about L0 suitability — but the 7 adopters only prove the bus
works; they don't prove it deserves L0 status. The bar is higher for
Phase C, and 7 internal adopters don't clear it.

This is the core reason Path C (Defer) is the correct choice: the
evidence we have is sufficient for Phase B, but not for Phase C.

---

## Decision (to be made in R71)

This ADR is DRAFT. The decision is made in R71, in a separate
recommendation memo: `.omo/_delivery/r71-phase-c-recommendation-memo.md`.

Options for the R71 memo:
- A: Path A (Strict)
- B: Path B (Pivot, file ADR-0008.2)
- C: Path C (Defer)

Default if no decision: Path C (the safest, the cheapest, the
governance-honest).

---

## References

- `projects/agora/docs/ADR-0008-bus-foundation-strategy.md` — original
  Phase C trigger definition
- `docs/ADR-0008.1-condition4-proxy.md` — R65 amendment (Phase B
  precedent)
- `docs/superpowers/plans/2026-06-12-bus-unification.md` — Phase C
  description
- `.omo/_delivery/r66-monthly-evidence-2027-04-12.md` — R66 evidence
