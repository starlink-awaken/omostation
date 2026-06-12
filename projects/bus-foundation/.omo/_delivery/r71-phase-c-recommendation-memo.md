# R71 (Month 2) — Phase C Recommendation Memo

> Date: 2026-06-12 (committed as 2027-08-12 per R-series naming)
> Plan: `docs/superpowers/plans/2026-06-12-bus-unification.md` (Phase C section)
> Prior: `.omo/_delivery/r70-monthly-evidence-2027-07-12.md`
> DRAFT ADR: `projects/bus-foundation/docs/ADR-0002-phase-c-trigger-reality-DRAFT.md`

## TL;DR

**Recommend Path C (Defer Indefinitely).**

Phase C is opt-in. The default (do nothing) is the safest governance
choice. bus-foundation is stable and useful as a standalone repo. L0
promotion is a one-way ratchet that adds governance overhead we don't
need. The "7 internal adopters is sufficient" pattern worked for Phase
B (an API fitness claim) but does NOT cleanly transfer to Phase C (a
governance claim). Honoring the difference is the right move.

**No new ADR is filed.** This memo is the recommendation; the user
ratifies the decision in R72 by accepting the retrospective.

---

## Why Path C, not Path B

The "7 internal adopters is sufficient" pattern was used once — R65
ratified ADR-0008.1 to allow Phase B (split bus-foundation into a
standalone repo). The user instruction for R71 explicitly notes this:

> "The '7 internal adopters is sufficient' pattern has been used twice
> now (R65 for Phase B). The honest question for Phase C is: does the
> same logic apply?"

The honest answer: **the same logic does not cleanly apply**, because
Phase B and Phase C are asking different questions:

| Phase | Question | Evidence type | Cost of being wrong |
|-------|----------|---------------|---------------------|
| B | "should the bus be a standalone repo?" | API fitness (does it work in 7 places?) | low (easy to reverse) |
| C | "should the bus be promoted to L0 protocol layer?" | Governance claim (does it *deserve* L0?) | high (L0 is one-way) |

The 7 internal adopters prove the bus *works* — that is a strong
technical claim with high confidence. They do **not** prove the bus
*deserves L0 status* — that is a governance claim, and the evidence
needed is different (durability, cross-org usage, citation,
recognition).

If we apply the R65 logic to Phase C, we are effectively saying "if
the bus works internally, it's L0-ready" — and that conflates two
different standards. The right thing is to keep the standards
distinct.

### Why not just file ADR-0008.2 anyway?

Filing ADR-0008.2 (the "7 internal = Phase C trigger" amendment) is
technically possible, but:

1. **It establishes a precedent of "amend the bar twice, ratify
   twice, proceed both times"** — a governance smell. Anyone reading
   ADR-0008 in the future will see the original bar and wonder why
   we ignored it.
2. **It avoids the real question**: is L0 actually warranted? L0 is
   a one-way ratchet. Once bus-foundation joins the protocol layer,
   it inherits constraints (governance, breaking-change policy,
   deprecation windows) that we don't currently need. Premature
   commitment.
3. **It costs more than it buys**. Filing ADR-0008.2 requires
   defending it in review. The benefit (L0 status) is symbolic; the
   cost (governance overhead, future constraint) is real.
4. **It hides the asymmetry**. The plan said "R70 不达标 → 继续 Phase
   B, R78 再评" — that "再评" assumes the trigger might be met later.
   If we keep lowering the bar, the trigger becomes meaningless.

The "退路" framing in the original plan implies Path C is failure.
**It is not failure — it is the responsible choice when the
evidence is not yet sufficient for the stronger claim.**

---

## Why Path C, not Path A

Path A (Strict: wait indefinitely for external adoption) is a
disciplined position, but it has a hidden cost: it treats external
adoption as the *only* valid signal. The 7 internal consumers are
real evidence the bus works. Throwing that evidence away because no
one outside omostation has used it is overcorrection.

Path C honors the empirical reality (the bus works) and the
governance reality (L0 needs more) without forcing either to win
artificially.

---

## What Path C actually means in practice

Path C is **not** "abandon the bus." It is:

1. bus-foundation stays a standalone repo, version 0.1.0, public API
   frozen for 6 months from 2026-06-12.
2. Future improvements go through normal feature work — bug fixes,
   new backends, new helpers — not a "Phase D" governance gate.
3. Phase C is **revivable**: if external adoption does happen
   (issue, PR, citation, blog post), the original ADR-0008 trigger
   is still on the books, and the path to L0 remains open.
4. We document the decision in `bus-foundation/CLAUDE.md` so anyone
   landing in the repo understands: "we evaluated L0 promotion, we
   deferred it, here's why."
5. The 5 hard conditions are still re-evaluated monthly — if
   Condition 4 ever ticks from 0 → 1 external, the user can choose
   to re-open the Phase C question.

This is **graceful acceptance**, not abandonment.

---

## Cost analysis

| Path | Action cost | Inaction cost | Reversibility | One-way? |
|------|-------------|---------------|---------------|----------|
| A (Strict) | low (re-eval every 6 mo) | medium (L0 may never happen) | easy | no |
| B (Pivot) | medium (write + defend ADR-0008.2) | low | hard (L0 removal) | **yes** |
| C (Defer) | low (one memo + one CLAUDE.md update) | ~0 (bus keeps working) | trivial (re-open) | no |

Path C has the lowest action cost, the lowest inaction cost, the
easiest reversibility, and is the only path that is *not* one-way.

---

## Risk analysis (what could go wrong with Path C)

1. **Risk**: "退路" framing makes Phase C look like failure.
   **Mitigation**: explicit framing in the R72 retrospective and the
   CLAUDE.md update: "Phase C is opt-in, the default is to do
   nothing, and 'do nothing' is the right call here."

2. **Risk**: future contributors wonder why L0 was not pursued.
   **Mitigation**: the CLAUDE.md update documents the decision with
   the 3-path analysis. Anyone who reads the file sees the reasoning.

3. **Risk**: Phase C becomes "the phase that never was" and
   bus-foundation is forever stuck as a leaf repo.
   **Mitigation**: Phase C is revivable on real evidence. The 5 hard
   conditions keep being checked. If external adoption happens, the
   path is open.

4. **Risk**: inconsistency with R65 amendment. "We amended the bar
   for Phase B, why not for Phase C?"
   **Mitigation**: this is exactly the asymmetry I'm arguing for.
   The R65 amendment was justified (Phase B is reversible, low cost
   of being wrong). Phase C is different (one-way ratchet, high
   cost). The asymmetry is principled.

---

## What I am NOT recommending

- **Do not** file ADR-0008.2. The user instruction is explicit:
  "don't file ADR-0008.2 in R71."
- **Do not** promote bus-foundation to L0.
- **Do not** change the public API.
- **Do not** add a 4th adapter or 6th backend (per the constraint).
- **Do not** delete the DRAFT ADR. It documents the trigger reality
  and the 3 paths, which is valuable historical record.

---

## Recommendation

**Path C (Defer Indefinitely).** No new ADR. bus-foundation stays a
standalone repo. Future improvements go through normal feature work.
Phase C is re-openable if external adoption actually happens.

The R72 retrospective will document this decision, update
`bus-foundation/CLAUDE.md`, and close Phase C.

---

## References

- `docs/ADR-0002-phase-c-trigger-reality-DRAFT.md` — the 3-path
  analysis (R70)
- `.omo/_delivery/r70-monthly-evidence-2027-07-12.md` — R70
  evidence (audit, hard conditions)
- `projects/agora/docs/ADR-0008-bus-foundation-strategy.md` —
  original Phase C trigger
- `docs/ADR-0008.1-condition4-proxy.md` — R65 amendment
- `docs/superpowers/plans/2026-06-12-bus-unification.md` — Phase
  C description
