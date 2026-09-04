---
title: "runbook-p74-silent-workflow"
type: runbook
owner: governance-team
lifecycle: contract
last_updated: 2026-08-23
---
# Runbook: P74 Silent Workflow Detected

## Symptom
- `make gac-local-gate` exits 1 with:
  ```
  [FAIL] p74-silent-workflows :: bin/gac/check-silent-workflows.py
  ```
- `bin/agent-workflow.py compliance` shows:
  ```
  P74 solidification: [WARN] N silent workflow(s)
  ```
- Gate fails in **default mode** since PR #2035 (was ci_only before)

## What is P74 silent?

ADR-0130 defines a workflow as "silent" when:
- `has_recent_run == False` (no agent_workflow_start event in the last
  `warn_after_days` window for the workflow's `run_frequency`)
- `has_check_coverage == False` (not referenced in any `diff_checks`
  or `doctor_checks`)

This means: the workflow is registered but no one runs it AND nothing
automatically checks its output. Either:
- The workflow is dead (should be removed)
- The workflow's owner stopped running it (regression)
- The workflow is new and not yet activated (transient)

## Diagnostic

```bash
# 1. Identify silent workflows
bin/gac/check-silent-workflows.py --list-silent

# 2. Inspect specific workflow
bin/gac/check-silent-workflows.py --json | python3 -c "
import sys, json
d = json.load(sys.stdin)
for w in d.get('silent_workflows', []):
    print(w)
"

# 3. Check workflow's run history
grep "agent_workflow_start" .omo/_delivery/agent-workflows/events.jsonl | \
  grep -i "<workflow_id>" | tail -5

# 4. Check if it has diff_check coverage
grep "<workflow_id>" .omo/_truth/registry/agent-workflows/_root.yaml
```

## Resolution

### Option A: workflow should be removed (dead)

If the workflow is no longer needed:
```bash
# 1. Edit .omo/_truth/registry/agent-workflows/_root.yaml
#    Remove the workflow entry from the workflows: list

# 2. Verify no consumers
grep -rl "<workflow_id>" --include="*.yaml" --include="*.py" bin/ docs/

# 3. Commit and push
```

### Option B: workflow is legitimate but no one runs it

Add `diff_checks` coverage so the gate stops complaining:

```yaml
# In .omo/_truth/registry/agent-workflows/_root.yaml
diff_checks:
  - id: <check_id>
    paths:
      - "<path-it-watches>"
    command: bin/gac/check-<something>.py
    workflow: <workflow_id>
```

The check provides evidence the workflow's intent is being satisfied
even without explicit runs.

### Option C: workflow is legitimate + has runs

If the workflow IS being run but the gate still flags it:
- Check `events.jsonl` freshness — `agent_workflow_start` events
  might be lost (file got truncated)
- Verify `run_frequency` matches actual cadence: `on_demand` (30d)
  vs `periodic` (7d) vs `continuous` (1d)
- Check timezone: gate uses `datetime.fromisoformat` — make sure
  events have proper `+00:00` or `Z` suffix

## Prevention

- **Don't register workflows you don't intend to run.** The cost of
  registering is cheap; the cost of an unattended silent workflow
  is a slow drift nobody catches.
- **Use `diff_checks` for compliance work.** If your workflow is
  about ensuring something (e.g. "test coverage must be ≥ 80%"),
  register the test as a `diff_checks` entry tied to the workflow.
- **Periodically review `silent_workflows`.** Run
  `bin/gac/check-silent-workflows.py --list-silent` weekly and
  decide each: remove, add coverage, or accept (rare).

## Related

- ADR-0130 (P74 workflow solidification)
- ADR-0211 §D1 (removed `excluded_workflows` escape hatch)
- PR #1971 (initial gate) and #2035 (promoted to default mode)
- `bin/gac/check-silent-workflows.py` — the check tool itself
- `bin/gac/check-silent-loss.py` — companion check (also gates)
- [`cleanup-rounds-2026-08-22.md`](cleanup-rounds-2026-08-22.md) — round 5 retrospective
