# ADR-0003: No L0 Protocol Layer Promotion

> Status: Accepted (R76, 2026-06-13)
> Deciders: bus-foundation maintainers
> Supersedes: (none — first formalization of R72 Path C Defer decision)

## Context

Per the original `agora/docs/ADR-0008-bus-foundation-strategy.md`,
bus-foundation was conceived as a stepping-stone toward L0 protocol
layer status. L0 is the highest tier in the eCOS architecture — it
implies the bus is a **protocol**, not just a library.

In R70-R72 (Phase C evaluation), we audited whether to proceed
with L0 promotion. The audit came back with:

- 0 external organizations using bus-foundation
- 0 external issues referencing bus-foundation
- 0 external PRs against bus-foundation
- INTENT issue (`starlink awaken/omostation#1`) open for 8 months
  with 0 comments

The 7 eCOS-internal consumers (omo, metaos, runtime, aetherforge,
kairon-pipeline, llm-gateway, hermes-console) are real, but
**internal** is not **protocol-level**.

## Decision

**bus-foundation will NOT be promoted to L0 protocol layer status.**

This is a final, not provisional, decision. The reasons:

### 1. L0 is a one-way ratchet, not a status to claim

L0 status in eCOS means: this is part of the protocol, breaking
changes are forbidden, and consumers include the entire monorepo.
Once granted, removing L0 is expensive (every consumer has to be
re-migrated). The asymmetry is: granting L0 is irreversible, but
**declining** L0 today doesn't close the door.

### 2. The 7-internal-consumer signal is sufficient for "the bus works"
but not for "the bus deserves L0 status"

L0 claims an API is fit for protocol-level adoption. Protocol-level
adoption means *external* users commit to depending on the bus.
Internal adoption is great evidence for API stability and design
soundness, but it does not test the same conditions as external
adoption would:

- Internal consumers can be coordinated. External consumers
  cannot.
- Internal consumers have other in-house backstops. External
  consumers are the only backstop.

### 3. The original trigger was always aspirational

"≥2 external orgs OR ≥1 academic citation" was not achievable by
the team that owns the project. The ADR-0008.1 amendment accepted
a proxy for Phase B, but proxy amendments should be one-shot.
Doing the same for Phase C would set a bad precedent.

## Consequences

**Positive**:
- bus-foundation stays as a normal standalone package, with normal
  feature work cadence
- No 1-way governance commitment that we cannot keep
- Future external adoption is still possible: if a real external
  org materializes, this ADR can be superseded (it explicitly
  leaves the door open — see "Re-opening this decision" below)

**Negative**:
- Some stakeholders may interpret "no L0" as "the bus is unimportant"
  — this is wrong; the bus is a critical internal library, just
  not a protocol
- A future maintainer may need to read this ADR + R72 retrospective
  to understand why L0 was declined. Mitigated by CHANGELOG.md
  and GOVERNANCE.md cross-references.

## Re-opening this decision

This ADR can be superseded if ALL of the following become true:

1. ≥2 distinct external organizations use bus-foundation
2. ≥1 academic citation of bus-foundation
3. bus-foundation has been stable (no breaking changes) for
   ≥12 months from the date of this ADR
4. The bus-foundation maintainer team (see OWNERS.md) explicitly
   requests re-evaluation

The bar is higher than the original ADR-0008 trigger (added 3 and 4)
because L0 is one-way and we want to be sure before committing.

## References

- Original plan: `docs/superpowers/plans/2026-06-12-bus-unification.md`
- ADR-0008 (Phase B trigger): `../agora/docs/ADR-0008-bus-foundation-strategy.md`
- R72 retrospective (Path C decision): `.omo/_delivery/r72-final-retrospective-2027-09-12.md`
- R71 recommendation memo: `.omo/_delivery/r71-phase-c-recommendation-memo.md`
- ADR-0002 (DRAFT trigger reality, R70): `docs/ADR-0002-phase-c-trigger-reality-DRAFT.md`
- GOVERNANCE.md §"What bus-foundation is NOT"
- CHANGELOG.md §"Backlog" (R75-ADR-0003)
