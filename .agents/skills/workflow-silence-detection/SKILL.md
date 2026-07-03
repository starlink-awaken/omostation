---
name: workflow-silence-detection
description: "Detect silent agent workflows (registered in agent-workflows.yaml but with no recent activity). Use when running governance audits, seeing P74 warnings in compliance output, or planning workflow consolidation. Triggers on: silent workflow, workflow solidification, P74, p74_solidification, compliance warn, governance drift."
---

# Workflow Silence Detection — P74 Solidification

The skill for diagnosing and resolving silent workflows per ADR-0130.

## When To Use

- `agent-workflow compliance --json` reports `p74_solidification.warn_count > 0`
- `make gac-local-gate` shows CR-P74-* check failures
- You're reviewing `agent-workflows.yaml::workflows` and wondering which entries are actually used
- You see `bin/agent-workflow.py suggest` reporting `uncovered_files`
- You're consolidating or retiring workflows

## The Workflow

### Step 1: Read the P74 report

```bash
cd /Users/xiamingxing/Workspace
uv run --with pyyaml python bin/agent-workflow.py compliance --json | python3 -c "
import json,sys
d=json.load(sys.stdin)
p74=d['p74_solidification']
print('P74 ok:',p74['ok'],'warn:',p74['warn_count'],'/',p74['summary_count'])
for w in p74['workflows']:
    if w['silent_health']!='active':
        print(f'  - {w[\"workflow_id\"]}: {w[\"silent_health\"]} '
              f'(run={w[\"has_recent_run\"]}, check={w[\"has_check_coverage\"]})')
"
```

Identify which workflows have `silent_health: warn`. These are the candidates for action.

### Step 2: Diagnose each silent workflow

For each warn workflow, run:

```bash
# Look at workflow definition
rg -A 20 "id: <workflow_id>" .omo/_truth/registry/agent-workflows.yaml
```

Determine:
- Is `has_check_coverage` true? → It's covered by a diff_check or doctor_check. This is **A2 silence** (intentional, the gate covers it).
- Is `has_check_coverage` false? → It's truly silent. This is **A1 silence**.

### Step 3: Apply the decision tree

See `.omo/standards/p74-solidification-contract.md` §3.3 for the canonical decision tree.

Summary:

| Type | Action |
|------|--------|
| A1 (no check coverage) | Add a `diff_checks` rule covering its surfaces, OR mark `excluded_workflows`, OR delete the workflow entry |
| A2 (check coverage only) | Document why it's A2, OR remove it if no longer relevant |
| Genuinely needed but unused | Trigger via `agent-workflow start` for a real scenario, OR add to `excluded_workflows` with rationale |

### Step 4: Verify the fix

After applying changes:

```bash
uv run --with pyyaml python bin/agent-workflow.py compliance --json | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('P74 ok:',d['p74_solidification']['ok'])
"
make gac-local-gate  # confirm 26+ checks still PASS
```

## Common Pitfalls

- **Don't** force `start` for a workflow that has no real use case. A2 silence is often correct.
- **Don't** add to `excluded_workflows` without understanding why it's silent. Excluded is for "intentionally not triggered by humans" workflows like `handoff-resume`.
- **Don't** delete a workflow entry without first checking what gate checks depend on it. Removing `mof-state-bridge-audit` would break the `mof-state-bridge` check.
- **Don't** change `silent_workflow_policy.warn_after_days` to silence the warnings. The threshold is a forcing function.

## Related

- ADR: `.omo/_knowledge/decisions/0130-p74-workflow-solidification.md`
- Pattern: `.omo/_knowledge/patterns/p74-workflow-solidification-pattern.md`
- Standard: `.omo/standards/p74-solidification-contract.md`
- SSOT: `.omo/_truth/registry/agent-workflows.yaml::silent_workflow_policy`
- GaC rules: `CR-P74-WORKFLOW-SILENCE`, `CR-P74-STATE-PROJECTION-GUARD`, `CR-P74-RUNTIME-STAMP-POLICY`
- Companion skills: `project-governance`, `governance-ssot-edit`, `governance-phase-orchestrator`

## Example Session

```
# Run compliance
$ uv run --with pyyaml python bin/agent-workflow.py compliance --json
P74 ok: False warn: 1 / 12
  - c2g-spec-ingress: warn (run=False, check=False)

# Diagnose: A1 silence
$ rg -A 10 "id: c2g-spec-ingress" .omo/_truth/registry/agent-workflows.yaml
# ... no diff_check or doctor_check covers projects/c2g/**

# Apply: add diff_check
$ # edit agent-workflows.yaml::diff_checks to include:
$ # - id: c2g-bet-help-coverage
$ #   paths: [projects/c2g/**]
$ #   command: [uv, run, --project, projects/c2g, c2g, bet, --help]

# Verify
$ make gac-local-gate
GaC local gate: PASS (27 checks executed, ALL GREEN)

$ uv run --with pyyaml python bin/agent-workflow.py compliance --json
P74 ok: True warn: 0 / 12
```