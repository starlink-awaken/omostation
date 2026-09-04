---
status: active
lifecycle: entry
owner: governance-team
last-reviewed: 2026-09-03
last_updated: 2026-09-03
type: doc
---

# T1-06 Milestone and Vision Gates Implementation Plan

**Goal:** Add derived Milestone/Campaign/Objective/Vision predicates to the
existing chain-bind authority without allowing agents or projections to write
completion or value state.

**Files:**

- Modify: `bin/plan/chain_bind.py`
- Modify: `bin/plan/chain-bind-check.py`
- Modify: `bin/plan/bet-ledger.py`
- Modify: `tests/test_chain_bind.py`
- Create: `tests/test_bet_portfolio_completion.py`

**Authorization gate:** implementation begins only after a distinct T1-06
authorization; planning authority never permits completion/value edits.

### Task 1: Write false-close RED cases

- [ ] Add fixtures where all leaves are done but one required KR is unproven,
  a value-exempt BET attempts to advance value, a replacement covers a failed
  leaf, an eleven-week window attempts Vision close, weekly accepted-output
  or acceptance-rate thresholds are missed, edit-burden fails to improve, and
  a human verdict is absent; add a Milestone fixture with an unresolved blocker
  and assert `MILESTONE_FALSE_CLOSE`, zero source/state mutation, and no
  derived met result.
- [ ] Add false-close fixtures where a required Campaign is unmet and where a
  required Objective is unmet; assert each blocks its parent predicate even
  when every leaf BET is terminal.
- [ ] Add independent synthetic-evidence and principal-unbound-human-evidence
  fixtures; both must fail before any Ledger/OMO/evidence write occurs.
- [ ] Assert exact failures: `MILESTONE_FALSE_CLOSE`,
  `VISION_WINDOW_INCOMPLETE`, and `VALUE_PROXY_REJECTED`.
- [ ] Run RED exactly:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_bet_portfolio_completion.py -q
```

### Task 2: Implement read-only derivation

- [ ] Add pure functions returning structured predicates, not status mutation:

```python
def evaluate_milestone(milestone: dict, ledger: dict, evidence: dict) -> Verdict: ...
def evaluate_vision(vision: dict, objectives: list[Verdict], window: list[dict]) -> Verdict: ...
```

- [ ] Require mandatory BET completion/replacement, proven KRs, zero unresolved
  blocker, zero P0 breach,
  every mandatory Campaign and Objective derived met, real-only evidence
  partition, twelve consecutive weeks, weekly accepted
  output threshold, acceptance-rate threshold, edit-burden improvement, and
  final human verdict for Vision.
- [ ] Preserve existing BET `evaluate_complete` behavior and completion-axis
  semantics; no helper writes Ledger, OMO state, or evidence.

### Task 3: CLI and regression proof

- [ ] Add a read-only `chain-bind-check` portfolio command returning canonical
  JSON verdicts and typed reasons.
- [ ] Run GREEN exactly:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_chain_bind.py tests/test_bet_portfolio_completion.py -q
uv run --with pyyaml python bin/plan/chain-bind-check.py self-check
uv run --with pyyaml python bin/plan/bet-ledger.py lint
```

Expected: all new false-close and value-proxy cases fail typed; valid fixtures
pass without source mutation.

### Rollback

Remove higher-level predicate entry points only. Existing BET-level chain-bind
logic and recorded evidence remain unchanged.
