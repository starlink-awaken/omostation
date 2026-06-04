# Phase 9 Wave 3 closeout

## Verdict

**GO** — Wave 3 established a working cross-root identity / authorization / admission control chain. The workspace now has an explicit identity anchor, machine-checkable action taxonomy, admission matrix, execution-context binding, evaluator seam, and a live governance-routed approval example for `project.dispatch`.

## What closed

1. `spaces/` now carries the first governed identity/admission contract, rooted in actor + space membership.
2. `system-space` now exposes a machine-checkable capability taxonomy and admission matrix for cross-root actions.
3. worker envelopes now bind `space_ref`, `membership_ref`, `action`, `admission_contract_ref`, `required_capabilities`, and `decision_mode`.
4. `scripts/omo_admission.py` now evaluates routed work against membership capability bindings and the admission matrix.
5. `python3 scripts/omo_worker.py worker admission-request-approval ...` now creates a worker approval record and a governance proposal for `conditional_approval`.
6. the sample Wave 3 `project.dispatch` path has been pushed through the governance chain to a verified approval artifact.

## Evidence

1. `spaces/_schema/space-identity-admission.schema.yaml`
2. `spaces/system-space-identity-admission.yaml`
3. `spaces/system-space-capability-taxonomy.yaml`
4. `spaces/system-space-admission-matrix.yaml`
5. `.omo/workers/templates/worker-task-envelope.yaml`
6. `.omo/workers/runs/phase9-wave3-identity-admission-envelope.yaml`
7. `.omo/workers/runs/phase9-wave3-identity-admission-approval.yaml`
8. `.omo/_truth/task-center/proposals/phase9-wave3-identity-admission-approval-proposal.yaml`
9. `scripts/omo_admission.py`
10. `scripts/omo_worker.py`
11. `.omo/tests/test_phase9_identity_admission_contract.py`
12. `.omo/tests/test_omo_admission.py`
13. `.omo/tests/test_omo_automation.py`

## Exit judgment

Wave 3 met its bar. Identity is no longer implied by path ownership, authorization language is explicit, and admission now has a real decision seam plus a governance escalation path for `conditional_approval`. Phase 9 can move to Wave 4 with a clear operational boundary instead of an abstract policy model.
