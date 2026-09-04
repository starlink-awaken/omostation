---
lifecycle: entry
owner: governance-team
last_updated: 2026-09-03
last_updated: 2026-09-03
type: doc
---

# T8-05 Cockpit Portfolio View Implementation Plan

**Goal:** Add a child-first, read-only Cockpit command family that presents
digest-bound Portfolio projections and never becomes a Ledger/Goals/OMO writer.

**Child-first files to select and claim after reading current Cockpit guidance:**

- Create/modify: `projects/cockpit/src/cockpit/commands/portfolio.py`
- Modify: `projects/cockpit/src/cockpit/_subcommands.py` and CLI registration
- Modify: `projects/cockpit/src/cockpit/cli.py`
- Create: `projects/cockpit/src/cockpit/tests/test_portfolio_command.py`
- Modify: `projects/cockpit/INTERFACE.yaml`

### Task 1: Start in the Cockpit child repository

- [ ] Read child `AGENTS.md`/`CLAUDE.md`, create an independent child clone,
  start `BET-Y1Q4-T8-05`, publish affected-graph receipt, and claim only the
  selected child paths.
- [ ] Add RED tests under `projects/cockpit/src/cockpit/tests/` for `status`,
  `objectives`, `critical-path`, and `blockers` using a digest-bound fixture.
- [ ] Add a dispatch test asserting `cockpit portfolio <subcommand>` is
  registered in `cli.py` and reaches the portfolio handler.
- [ ] Add a hostile static-and-runtime test: monkeypatch all Ledger, Goals,
  and OMO state write entrypoints; any import/call from the command must fail
  before an output is returned.
- [ ] Run RED exactly in the child:

```bash
uv run --with pytest python -m pytest \
  src/cockpit/tests/test_portfolio_command.py -q
```

### Task 2: Implement strict read-only consumption

- [ ] Load the registered control projection through one adapter; validate its
  source digest before formatting output.
- [ ] Return a stable `unavailable` result for missing, stale, malformed, or
  mismatched input. Never fall back to Ledger parsing or inferred status.
- [ ] Prohibit imports/calls that mutate Ledger, Goals, OMO state, BET/KR,
  Milestone, Campaign, or Vision.
- [ ] Make the hostile writer test pass only when all writer attempts raise;
  verify the handler loads no Ledger path even as a fallback.

### Task 3: Verify child then root pointer

- [ ] Run GREEN exactly in the child:

```bash
uv run --with pytest python -m pytest src/cockpit/tests/test_portfolio_command.py -q
uv run python -m cockpit.cli portfolio status --help
```

Expected: all four commands are registered, digest-bound, unavailable-safe,
and hostile writer attempts fail.
- [ ] Tag and merge child PR only after those checks pass.
- [ ] Prove child `origin/main` contains the source commit and only then open a
  standalone root gitlink pointer PR with reachability checks.
- [ ] Compare Cockpit output digest against the projection digest and run a
  fixed non-expert usability scenario.

### Rollback

Revert the child command first, then a separate root pointer successor if one
exists. Preserve Ledger/projection source evidence and all external state.
