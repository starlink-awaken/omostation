---
name: workflow-silence-detection
description: "Use when governance audits report silent workflows, P74 or p74_solidification warnings, compliance drift, or when planning workflow consolidation in the canonical split registry."

last-reviewed: 2026-08-26
type: ssot
owner: governance-team
---

# Workflow Silence Detection — P74 Solidification

The skill for diagnosing and resolving silent workflows per ADR-0130.

## When To Use

- `agent-workflow compliance --json` reports `p74_solidification.warn_count > 0`
- `make gac-local-gate` shows CR-P74-* check failures
- You're reviewing `.omo/_truth/registry/agent-workflows/workflows/` and wondering which entries are actually used
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
rg -A 20 "id: <workflow_id>" .omo/_truth/registry/agent-workflows/workflows
```

Determine:
- Is `has_check_coverage` true? → It's covered by a diff_check or doctor_check. This is **A2 silence** (intentional, the gate covers it).
- Is `has_check_coverage` false? → It's truly silent. This is **A1 silence**.

### Step 3: Apply the decision tree

See `.omo/standards/p74-solidification-contract.md` §3.3 for the canonical decision tree.

Summary:

| Type | Action |
|------|--------|
| A1 (no check coverage) | Add a real `diff_checks` rule covering its surfaces, or delete the workflow entry if it is obsolete |
| A2 (check coverage only) | Document why it's A2, OR remove it if no longer relevant |
| Genuinely needed but unused | Trigger via `agent-workflow start` only for a real scenario, or add executable check coverage |

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
- **Don't** recreate the removed exclusion mechanism. A workflow needs real run evidence, executable check coverage, or retirement.
- **Don't** delete a workflow entry without first checking what gate checks depend on it. Removing `mof-state-bridge-audit` would break the `mof-state-bridge` check.
- **Don't** change `silent_workflow_policy.warn_after_days` to silence the warnings. The threshold is a forcing function.

## Related

- ADR: `.omo/_knowledge/decisions/0130-p74-workflow-solidification.md`
- Pattern: `.omo/_knowledge/patterns/p74-workflow-solidification-pattern.md`
- Standard: `.omo/standards/p74-solidification-contract.md`
- SSOT: `.omo/_truth/registry/agent-workflows/_root.yaml::silent_workflow_policy`
- GaC rules: `CR-P74-WORKFLOW-SILENCE`, `CR-P74-STATE-PROJECTION-GUARD`, `CR-P74-RUNTIME-STAMP-POLICY`
- Companion skills: `project-governance`, `governance-ssot-edit`, `governance-phase-orchestrator`

## Example Session

```
# Run compliance
$ uv run --with pyyaml python bin/agent-workflow.py compliance --json
P74 ok: False warn: 1 / 12
  - c2g-spec-ingress: warn (run=False, check=False)

# Diagnose: A1 silence
$ rg -A 10 "id: c2g-spec-ingress" .omo/_truth/registry/agent-workflows/workflows
# ... no diff_check or doctor_check covers projects/c2g/**

# Apply: add diff_check
$ # edit agent-workflows/_root.yaml::diff_checks to include:
$ # - id: c2g-bet-help-coverage
$ #   paths: [projects/omo/src/omo/_vendored/c2g/**]
$ #   command: [uv, run, --project, projects/omo, c2g, bet, --help]

# Verify
$ make gac-local-gate
GaC local gate: PASS (27 checks executed, ALL GREEN)

$ uv run --with pyyaml python bin/agent-workflow.py compliance --json
P74 ok: True warn: 0 / 12
```
