---
status: ACTIVE
lifecycle: telos
owner: governance-team
last-reviewed: 2026-07-09
related:
  - TAXONOMY.md
  - zones.yaml
  - ../CLAUDE.md
  - ../../../AGENTS.md
  - ../../../BRIEF.md
---

# TELOS — The North Star of omostation

Adapted from PAI/LifeOS's TELOS structure. 6 sections, each 200-500
words. This is **the single source of truth** that the LLM reads at
session start to align every decision. All agent recommendations
should cross-reference these sections.

> Why 6 sections? They match PAI's TELOS pattern AND map to existing
> omostation artifacts (see `TAXONOMY.md` §11 for the full mapping).
> Each section is *short* by design — if any section grows past 500
> words, that's a signal to split it into an ADR.

---

## 1. MISSION — Why we exist (North Star)

omostation is the **meta-system for AI agents to coordinate, observe,
and improve themselves** across 8+ consumer projects via a shared
bus-foundation backbone.

Three concrete promises this mission makes:

1. **Bus-foundation is the single integration point.** Every consumer
   project (agora, omo, metaos, aetherforge, runtime, cockpit,
   l4-kernel, kairon-pipeline) talks to the rest of the world
   through `bus_foundation.facade.{event,control,data}`. Not through
   ad-hoc HTTP, not through ad-hoc SSE, not through git submodules
   serving as ad-hoc APIs. One bus, three planes, no exceptions.

2. **Dormant code is dead code.** A consumer that declares
   bus-foundation in its dependencies but has no production call
   site is a **P71 class-A trap** — the declaration lies. Our
   `bin/bus-usage-report.py` gate ensures every declaration is
   followed by reality. (P7x rollout lesson: 8/8 consumers
   dormant at 0.3.0 release. Never again.)

3. **AI agents self-improve through structured feedback.** The
   `agent-workflows` system records every workflow run as
   `runs/{run-id}.yaml`. The 7-phase Algorithm (Observe→Learn)
   becomes a habit, not a ceremony: we observe, decide, build,
   verify, learn — and **each phase has an artifact in `.omo/`**.

---

## 2. GOALS — What success looks like (12 months)

| Goal | Current | Target | Measurement |
|---|---|---|---|
| **Every consumer has ≥1 production bus call** | 8/8 ACTIVE | 8/8 + new | `bin/bus-usage-report.py` |
| **Cross-project change ships in ≤1 week** | varies | median ≤7d | `git log --since` per cross-project commit |
| **Pre-commit gates catch 90% of regressions** | ~50% | 90% | `bin/bus-usage-report` + `bin/gac-local-gate` failure-rate over 100 PRs |
| **Dormant code ratio** | 0% (8/8 active) | 0% | weekly `bin/bus-usage-report` run |
| **Submodule pointer drift** | 1 incident (4d0dc5c5) | 0/quarter | `bin/bus-usage-report` + zones-check |
| **AI agent onboards a new project in ≤1 hour** | ~2 hours | ≤1 hour | PAI Pack standardization |
| **CI total time** | ~50 min | ≤15 min | `gh pr checks --json` |

---

## 3. BELIEFS — Non-negotiable principles (3 only)

**These are absolute. If a change violates a belief, the change is
wrong, not the belief.**

### B1. Dormant code is dead code

A dependency declared but not used is a lie. If we say
`bus-foundation = ["ws", "redis", "zmq"]` but the consumer code
never calls `bus_event.publish(...)`, the dependency must be removed
or the integration must be completed. **No "we might use it later".**
The P7X bus-foundation rollout exposed this: 8/8 consumers dormant
at the 0.3.0 release. (See `BRIEF.md` and ADR-0180.)

### B2. Submodule pointer in main = reachable commit

A `projects/{name}` pointer in the main repository **must** reference
a commit that exists on that submodule's `origin/main`. No WIP,
no local-only commits, no "I'll push later". The P7X rollout
discovered commit `4d0dc5c5` (runtime) was referenced from main
but never pushed to origin — CI failed with "could not read
Username for 'https://github.com'". The fix: every PR that bumps a
submodule pointer must verify `git ls-remote origin <submodule> <sha>`
returns the SHA **before** pushing. The `bin/bus-usage-report` gate
plus `zones-check` will enforce this.

### B3. Test the contract, not the implementation

Every public API (bus-foundation, omo cli, agora routes) has a
contract — input shape, output shape, error semantics. Tests must
verify the contract, not the specific implementation details.
**P7X lesson**: `test_zmq_backend.py` was written to verify the
contract (publish-subscribe round-trip with no loss), not the
internal queue mechanics. When the implementation changed, the
tests stayed valid.

---

## 4. WISDOM — Lessons from the past

Five hard-won lessons. Each one came from a real failure, not
speculation.

### W1. Pre-existing failures are real failures

CI gates that have been "failing for 4 months" are not noise —
they are signals we ignored. (P7X: governance-semantic-gate had
`adr-coverage` and `release_ready=false` failures that pre-dated
the rollout. They blocked PR #309 for 6+ hours until we fixed
them in a separate PR.) **Action**: every CI failure must be
classified (blocker vs. noise) and either fixed or quarantined
within 1 week.

### W2. Submodule SSOT can be silently overridden

`gac-local-gate.py` originally had a `governance-evolution` check
defined in **the submodule** (ecos). The submodule's main branch
got force-pushed and the check disappeared. **Action**: defense in
depth — every check that the **main repo** needs must be registered
in the main repo's `gac-local-gate.py` DEFAULT_POLICY. The submodule
SSOT is a backup, not the primary.

### W3. Lazy optional-dep imports prevent `import` failures

bus-foundation pre-0.3.1 imported `import zmq` at module top
inside `zmq.py`. Every consumer that didn't install pyzmq failed
at import time. **Action**: optional extras (zmq, redis,
websockets) use lazy imports via `_require_zmq()` or PEP 562
`__getattr__`. `import bus_foundation` succeeds in any environment.

### W4. Pre-commit hooks check the wrong thing

A pre-commit hook that runs `ruff check projects/*/src` is not the
same as running it on the right files. We have had multiple
incidents where the hook ran but missed a violation because the
file path glob was too narrow. **Action**: pre-commit hooks should
run **all** governance checks (`make ci-local-fast`) not just
syntax.

### W5. Dormant adapters are easy to create, hard to find

Once a project declares `bus-foundation = [...]` in pyproject.toml
but has no real call site, it looks "complete" but is actually
lying. The P7X rollout found 8/8 consumers in this state. **Action**:
`bin/bus-usage-report.py` runs in non-strict pre-commit and CI strict,
exits 1 on any dormant consumer. (Created in P7X bus-foundation-rollout.)

---

## 5. MENTAL_MODELS — How we think about systems

Three models. Each shapes how we reason about new problems.

### M1. Multi-submodule monorepo ≈ distributed system

`projects/agora`, `projects/omo`, `projects/runtime` etc. are
**separate repositories with separate CI lifecycles, but they share
a root pointer and a cross-cutting protocol (bus-foundation)**. A
PR that bumps a submodule pointer is a **versioned contract** between
root and child. The root has no authority over the child's history
after the pointer moves.

Implication: when changing a cross-project behavior, **start at the
child** (where the behavior lives) and **end at the root** (where
the pointer lives). The reverse breaks the contract.

### M2. CI failure is a signal, not noise

Every CI failure has an owner. Every "we'll fix it later" failure
becomes a permanent tax. The P7X rollout found 4-month-old failures
that blocked every PR until fixed. (P7X: governance-semantic-gate
`adr-coverage`, `governance-evolution-packages`, port hardcode
`8766`, omo_batch1 test file references.)

Implication: **first commit on any PR** should be the one that fixes
or quarantines the pre-existing CI failures. Then add the new
feature. Never build new on top of broken.

### M3. Containment zones are not negotiable

`.omo/_control/`, `.omo/_knowledge/decisions/draft/`, runtime
state — these are **internal** artifacts. They MUST NOT appear in
public releases. PAI enforces this with regex path rules; we now
do the same via `zones.yaml` + `zones-check.py` (added in this
rollout).

Implication: if a path starts with `.omo/`, `state/`, or any
containment zone prefix, it is internal. If it's internal, it does
not go in public docs, public releases, or public CI artifacts.

---

## 6. STRATEGIES — How we execute (3 strategies, not a roadmap)

PAI has 5 strategies; we have 3. They are **durable patterns**, not
project plans. Each project plan (in `docs/proposals/` or
`.omo/_knowledge/plans-archive/`) consumes one or more of these
strategies.

### S1. The 3-phase rollout for any cross-cutting change

Every time a change crosses 2+ submodules (e.g. bus-foundation
rollout = bus-foundation + cockpit + runtime + ecos + workspace),
follow:

1. **SSOT in child first.** Implement the behavior in the child
   submodule (bus-foundation). Commit + push to origin. (P7X: 0.3.0
   → 0.3.1 with all the new features.)
2. **Wire-up in consumers.** Add calls in each consumer (omo,
   metaos, aetherforge, runtime). Commit + push each one.
3. **Root pointer + workspace tools.** Bump the main repo's
   submodule pointers in a single commit, and add any new
   workspace-level tools (bin/bus-usage-report.py, ADR-0180). Push
   to a new branch, run PR CI, merge.

This 3-phase rollout **prevents the 4-month-old-failure problem** by
making each phase independently testable.

### S2. The dormant-adapter guard

For any dependency declared in `pyproject.toml` or `package.json`:
the **first commit** on its adoption must include either a real
production use site OR a comment justifying why it's listed for
forward-compatibility. P7X invented `bin/bus-usage-report.py` for
this. It runs in pre-commit (non-strict) and CI (strict). Every
project that declares a dependency is held to this.

### S3. The "one commit, one purpose" rule

Every commit does one thing. **No "drive-by" submodule pointer
bump in a feature commit.** If a PR changes behavior in two places,
split it. The P7X rollout had 7 PRs:
- PR #306 (bump kairon)
- PR #309 (workspace files)
- PR #314 (omo cleanup)
- PR #318 (kairon G1-G5)
- PR #322 (gate unlock)
- PR #326 (workspace files + ADR-0180)
- PR #328 (submodule bumps)

This **7-PR pattern** made each failure isolated and fixable in
isolation. Contrast with a single mega-PR that touches everything
and fails for 5 different reasons at once.

---

## Cross-references

- `TAXONOMY.md` — full mapping of omostation ↔ PAI concepts
- `zones.yaml` — containment zones (B1, B2, B3 enforcement)
- `../CLAUDE.md` — operational instructions
- `../../../AGENTS.md` — agent operating guide
- `../../../BRIEF.md` — current project state
- `../decisions/0180-bus-foundation-rollout.md` — P7X ADR (this rolltemplate's
  nearest ancestor)
- `../../../AGENTS.md#§6-round-workflow` — round workflow pattern (PR strategy)
