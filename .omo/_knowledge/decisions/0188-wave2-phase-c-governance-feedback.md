---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0188 — Wave 2 Phase C: C2G → OMO 治理提案联动（无自动改规则）

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + c2g

## Context

Phase A closed the outcome data loop; Phase B added forecast + heatmap.
Roadmap Phase C wanted “C2G Outcome → OMO 治理规则自动调整”. Full auto-mutation
of GaC / x1 policies is high-risk (policy thrash, audit gaps).

## Decision

**Proposal-first feedback loop** (not auto rule rewrite):

| Item | Choice |
|------|--------|
| Input | OutcomeTracker + Phase B forecast/heatmap |
| Output | JSON **proposals** (`risk_attention`, `strategy_review`, …) |
| CLI | `python -m c2g.governance_feedback` |
| Optional tasks | `--show-apply-plan` dry-run; `--apply-tasks` → OMO **planned** via broker |
| Forbidden | Auto-edit `.omo/_truth/**` policies / GaC rules |

`auto_mutate_rules: false` is a permanent field on the report contract for this ADR.

## Acceptance

| Check | Evidence |
|-------|----------|
| Empty baseline | `prop-empty-baseline` proposal |
| Critical heat | P0 `create_planned_task` proposal |
| Declining trend | P1 strategy review proposal |
| Dry-run tasks | `apply_proposals_as_tasks(..., dry_run=True)` |
| Tests | `pytest tests/test_governance_feedback.py` |

## Non-goals

- Auto-merge of GaC rules from forecast
- Direct write of x1-governance-policies.yaml
- Cockpit UI for proposals (JSON is the contract)

## Verification

```bash
cd projects/c2g
uv run pytest tests/test_governance_feedback.py -q
uv run python -m c2g.governance_feedback --data-dir /tmp/empty
uv run python -m c2g.governance_feedback --show-apply-plan
```

## References

- ADR-0183 / 0185
- `draft/WAVE2-C2G-OMO-ROADMAP.md`
- `projects/c2g/src/c2g/governance_feedback.py`
