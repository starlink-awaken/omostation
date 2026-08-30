---
id: ADR-0445
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-30
---

# ADR-0445: Agent Workflow Standardization

- **Status**: ACCEPTED
- **Date**: 2026-08-30
- **Authors**: governance-team
- **Supersedes**: (none)
- **Superseded by**: (none)

## Context and Problem Statement

ADR-0203 made agent workflows mandatory for requirement iterations, and ADR-0130 added P74 workflow solidification. Despite these rules, agents still bypass the workflow in practice: they edit files directly, skip the `start` step, or treat `observer-audit` as a write exemption. The enforcement gate (ADR-0204) catches staged requirement-path edits without an active run, but the workflow lifecycle itself has inconsistencies in how agents claim paths, verify results, and close out runs.

The problem: how to standardize the agent workflow lifecycle so that every agent follows the same claim-verify-closeout pattern, with machine-checkable evidence at each stage, reducing the variance that produces silent workflows and incomplete deliveries.

## Decision Drivers

* Every requirement iteration must have a traceable run (bootstrap, start, claim, verify, closeout)
* Path claims must be visible to other agents to prevent concurrent work on the same files
* Verification must produce machine-readable evidence (diff-based, not self-reported)
* Closeout must link to the originating bet/objective (ADR-0203 vision-to-retro chain)
* The standard must be enforceable by the existing `agent-workflow.py` runner without new infrastructure

## Considered Options

1. **Standardize on existing runner (agent-workflow.py) with stricter gates** — tighten the existing runner's claim/verify/closeout stages and add machine-checkable evidence requirements
2. **New workflow DSL** — design a declarative workflow language that agents compile to run records
3. **Git-based workflow tracking** — use git branches and PRs as the workflow lifecycle representation
4. **External workflow engine (Temporal/Airflow)** — adopt a production workflow engine

## Decision Outcome

**Chosen option: "Standardize on existing runner (agent-workflow.py) with stricter gates", because the runner already implements the lifecycle, has GaC integration, and the gap is enforcement rigor, not missing features.**

### Consequences

* Good: No new infrastructure, leverages existing GaC/OMO/Cockpit integration
* Good: Stricter gates catch bypass attempts at CI time, not after damage is done
* Good: Machine-readable evidence (diff-based verify) replaces self-reported completion
* Bad: Agents that previously relied on loose enforcement must adapt (breaking change for sloppy agents)
* Bad: Stricter gates may produce false positives on edge cases (mitigated by waiver escape hatch)

### Confirmation

```bash
# Verify the runner enforces the full lifecycle
uv run --with pyyaml python bin/agent-workflow.py compliance --json | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='pass'"

# Verify a run without claim is rejected
uv run --with pyyaml python bin/agent-workflow.py verify test-run-no-claim --from-diff --execute 2>&1 | grep "no claim"

# Verify closeout requires bet binding
uv run --with pyyaml python bin/agent-workflow.py closeout test-run-no-bet 2>&1 | grep "bet_id required"

# Full lifecycle smoke test
bash tests/integration/agent-workflow-lifecycle-smoke.sh
```

## Pros and Cons of the Options

### Standardize on existing runner with stricter gates

* Good: Incremental improvement, no migration risk
* Good: Existing GaC/CI integration works as-is
* Bad: The runner is already complex, adding gates increases complexity
* Bad: Legacy runs without strict gates may fail on re-verification

### New workflow DSL

* Good: Clean slate, expressive semantics
* Bad: Massive migration effort, every existing workflow must be rewritten
* Bad: Adds a compilation step and a new failure mode

### Git-based workflow tracking

* Good: Uses familiar git primitives
* Bad: Git branches are not designed for multi-stage workflows with evidence
* Bad: Conflates code review with workflow lifecycle, mixing concerns

### External workflow engine

* Good: Production-grade reliability, proven at scale
* Bad: Heavyweight dependency, requires deployment and maintenance
* Bad: Overkill for a single-host multi-agent workspace

## Rollback

If stricter gates produce excessive false positives:

1. Set `AGCP_REQUIREMENT_ITERATION_GATE=0` as the escape hatch (documented in ADR-0204).
2. Adjust gate thresholds via `governance-checks.yaml` without removing the gates entirely.
3. Re-enable gates incrementally per workflow type after tuning.
4. The runner's gate logic is configuration-driven, so rollback does not require code changes.

## References

* ADR-0203: requirement iteration mandatory workflow
* ADR-0204: executable gate + pre-push path + worktree/ADR claim
* ADR-0130: P74 workflow solidification
* `bin/agent-workflow.py` — the workflow runner
* `.omo/_truth/registry/agent-workflows/` — workflow SSOT
* `.omo/standards/agent-workflow-contract.md` — workflow contract
