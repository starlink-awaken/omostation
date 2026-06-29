---
name: project-governance
description: Use when an agent changes this workspace or a child project and needs executable governance workflow routing instead of relying on AGENTS.md or CLAUDE.md memory.
---

# Project Governance Workflow

This skill is a thin bootloader. The source of truth is:

- Registry: `.omo/_truth/registry/agent-workflows.yaml`
- Runner: `bin/agent-workflow.py`
- Contract: `.omo/standards/agent-workflow-contract.md`

## Required First Step

Run the workflow lint before making changes:

```bash
uv run --with pyyaml python bin/agent-workflow.py lint
```

## Choose A Workflow

List the available workflows:

```bash
uv run --with pyyaml python bin/agent-workflow.py list
```

Common routes:

| Work type | Workflow |
|-----------|----------|
| Root or project docs | `project-doc-change` |
| Code inside `projects/<project>` | `project-code-change` |
| `.omo` or `spaces` state mutation | `governance-state-mutation` |
| BMAD/OpenSpec/Pitch ingress | `c2g-spec-ingress` |
| Root submodule pointer closeout | `submodule-pointer-close` |
| Compressed or handed-off session | `handoff-resume` |

## Start Or Resume

For any multi-step task, create a run record before editing:

```bash
uv run --with pyyaml python bin/agent-workflow.py start project-doc-change \
  --actor "${USER:-agent}" \
  --objective "<short objective>"
```

After context compression or agent handoff:

```bash
uv run --with pyyaml python bin/agent-workflow.py resume "<run-id>"
uv run --with pyyaml python bin/agent-workflow.py handoff "<run-id>"
```

## Execute Stages

Print a stage plan without side effects:

```bash
uv run --with pyyaml python bin/agent-workflow.py run project-doc-change --stage preflight
```

Run non-manual commands in a stage:

```bash
uv run --with pyyaml python bin/agent-workflow.py run project-doc-change --stage verification --execute
```

Manual commands in the registry are intentional handoffs to the agent or the project-local docs. Do not pretend they ran.

## External Adapters

Check optional tool availability:

```bash
uv run --with pyyaml python bin/agent-workflow.py doctor
```

`bmad` and `openspec` are routed through C2G/OMO bridge commands when source files exist. `gstack` and `beads` are optional adapters and must degrade to advisory mode when missing.

## Closeout

When the task is complete:

```bash
uv run --with pyyaml python bin/agent-workflow.py handoff "<run-id>"
uv run --with pyyaml python bin/agent-workflow.py close "<run-id>" \
  --status ok \
  --evidence "<verification command or artifact>"
```

Do not create git commits unless the user explicitly requested commits.
