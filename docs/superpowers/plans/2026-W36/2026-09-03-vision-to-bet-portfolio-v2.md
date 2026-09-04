---
status: active
lifecycle: entry
owner: governance-team
last-reviewed: 2026-09-03
last_updated: 2026-09-03
type: doc
---

# W0 Portfolio/BET v2 Implementation Plan

> **For agentic workers:** execute each child in its own fresh workflow and
> independent clone. This parent plan coordinates; it never substitutes a
> child receipt, test, PR, or value claim.

**Goal:** Turn the accepted W0 Portfolio v2 contracts into one strict Ledger
mechanism that can express strategic hierarchy, prove coverage and completion,
produce one-way projections, and dogfood the complete non-value path.

**Architecture:** `docs/plans/3y-bet-ledger.yaml` remains the only portfolio
truth. T1-04 adds additive parsing and validation; T1-05 derives coverage and
critical path; T1-06 derives completion; T1-07 inventories legacy data;
T1-08 projects through registered ownership; T8-05 consumes the projection in
Cockpit; T1-09 proves the whole chain. No new service, database, dispatcher,
or value writer is allowed.

**Tech Stack:** Python 3.13, PyYAML, pytest, existing `bin/plan` CLIs,
Agent Workflow, OMO broker, Cockpit child repository, GitHub required checks.

## Global Constraints

- Parent BET: `BET-Y1Q4-T1-03`; child IDs and dependencies are immutable from
  the accepted binding.
- Every child starts `bootstrap → start --bet → affected receipt → claim` in
  a new independent clone. The parent never reuses this planning run for code.
- At most two writers per wave; no two writers touch the same file or child
  repository. Shared Ledger/self-binding/root-pointer work is serialized.
- Candidate status, completion axes, accepted bindings, human gates and value
  policy are never promoted by planning or tests.
- **Implementation hard-stop:** these plans are procedural artifacts only.
  Before any child calls `start`, claims a code/test/state path, or edits an
  implementation surface, a distinct implementation authorization must be
  recorded and the child Spec/binding must no longer say
  `implementation_authorized: false`. A planning-run claim never satisfies
  that gate.
- `value_indicator_policy=false` means value remains `NOT_PROVEN`; PR/CI/test
  success is delivery evidence only.
- A main advance touching Ledger, an accepted Spec, or a child write surface
  requires a fresh guarded baseline; non-overlapping advances require an
  explicit current-tree comparison before integration.

## Delivery Order

| Wave | BETs | Gate to leave wave |
|---|---|---|
| A1 | T1-04 | v1-compatible parser, RED/GREEN fixtures, no side effects |
| A2 | T1-05 + T1-07 | deterministic graph and manifest, no existing-BET mutation |
| B | T1-06 + T1-08 | derived completion and broker-owned projections |
| C | T8-05 | child-first Cockpit read-only consumer and root pointer proof |
| D | T1-09 | immutable positive canary plus complete negative matrix |
| Close | T1-03 | all four derived Milestones, exact-SHA replay, clone receipts |

## Mandatory T1-04 Self-Binding Sequence

T1-04 is not complete merely because its parser tests pass. Its required
sequence is: (1) merge additive validator with compatibility warning and
strict fixtures; (2) open a separately claimed one-field `meta.total_bets`
repair from immutable `len(bets)`; (3) verify strict full-Ledger mode on the
repair tree; (4) create a separately authorized W0 self-binding amendment that
replaces only `bootstrap_unenforced` declarations with enforced v2 fields,
without changing status, dependencies, accepted bindings, completion axes, or
value evidence. Semantic dependent children start only after step 4.

## Parent Coordination Tasks

### Task 1: Freeze child contracts before each implementation run

**Files:** Read the eight accepted Specs and the current Ledger only.

- [ ] Recompute each child accepted-Spec digest from the current merge tree.
- [ ] Run `bin/plan/bet-ledger.py claim-check <BET>` and compare its declared
  write surfaces to the child plan before starting a run.
- [ ] Use `bin/gac/affected-graph.py` with every changed project plus
  `workspace-root`; claim only the resulting plan/code/test paths.
- [ ] Halt when a digest, dependency, ID, or write surface differs; issue a
  bounded amendment instead of editing around the mismatch.

### Task 2: Execute waves without shared-truth races

- [ ] Run T1-04 alone and merge its child PR before starting T1-05/T1-07.
- [ ] Require the four-step validator → one-field repair → strict lint →
  self-binding sequence before starting a child that consumes enforced v2
  semantics; planning does not waive any one of the separate claims.
- [ ] For every child, prove the implementation-authorization gate before the
  child workflow starts; halt with `IMPLEMENTATION_AUTHORIZATION_MISSING` when
  the accepted binding remains planning-only.
- [ ] Start T1-05 and T1-07 only after their files and affected-project
  receipts are disjoint; do not let either modify existing BET objects.
- [ ] Serialize `bin/plan/bet-ledger.py`, `chain_bind.py`, and broker-owned
  `.omo` writes even if two child PRs are otherwise concurrent.
- [ ] Require child PR merge SHA, required contexts, source tag, and
  canonical clone retirement before advancing a downstream dependency.

### Task 3: Parent closeout

- [ ] T1-09 executes an immutable canary only after all implementation child
  receipts are available; it may not create W1-W6 or a value outcome.
- [ ] Recompute all four Milestone predicates and assert W0 Parent remains
  blocked until every required child predicate is satisfied.
- [ ] Run exact-tree structural comparison, accepted-Spec digest replay,
  `chain-bind-check.py self-check`, and required post-merge checks.
- [ ] Only a separately authorized parent completion transition may change
  T1-03 status; this plan itself supplies no completion evidence.

## Cross-Wave Rollback

Revert the smallest merged child PR that introduced the failed behavior. A
rollback may remove that child’s implementation/projection but never rewrites
historical BET truth, external evidence, value outcomes, or another child’s
merge. Re-run graph/coverage/completion checks after every revert.
