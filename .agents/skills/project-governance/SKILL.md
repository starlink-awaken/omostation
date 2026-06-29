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
uv run --with pyyaml python bin/agent-workflow.py agents
uv run --with pyyaml python bin/agent-workflow.py adapters
```

Common routes:

| Work type | Workflow |
|-----------|----------|
| Root or project docs | `project-doc-change` |
| Code inside `projects/<project>` | `project-code-change` |
| `.omo` or `spaces` state mutation | `governance-state-mutation` |
| BMAD/OpenSpec/Pitch ingress | `c2g-spec-ingress` |
| MOF M1/M2/M3 model change | `mof-model-change` |
| MOF schema/state bridge audit | `mof-state-bridge-audit` |
| BMAD/OpenSpec/beads/gstack/Superpowers sync | `external-adapter-sync` |
| Root submodule pointer closeout | `submodule-pointer-close` |
| Compressed or handed-off session | `handoff-resume` |
| Read-only run/lock/ledger audit | `observer-audit` |

The registered agent profiles are in `.omo/_truth/registry/agent-workflows.yaml::agent_profiles`.
Use them as role boundaries. If a workflow references an unregistered role, `agent-workflow lint`
must fail.

## Start Or Resume

For any multi-step task, create a run record before editing:

```bash
uv run --with pyyaml python bin/agent-workflow.py start project-doc-change \
  --actor "${USER:-agent}" \
  --profile governance-agent \
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
uv run --with pyyaml python bin/agent-workflow.py run project-doc-change \
  --profile governance-agent \
  --stage verification \
  --execute
```

Manual commands in the registry are intentional handoffs to the agent or the project-local docs. Do not pretend they ran.

## External Adapters

Check optional tool availability:

```bash
uv run --with pyyaml python bin/agent-workflow.py doctor
uv run --with pyyaml python bin/agent-workflow.py observe
```

`adapters` is the contract view: it declares each external tool's authority, ingress workflow,
SSOT rule, bridge command, and fallback. `doctor` is the health view.

`bmad` and `openspec` are routed through C2G/OMO bridge commands when source files exist. `gstack` and `beads` are optional adapters and must degrade to advisory mode when missing.
MOF changes use `.omo/_truth/registry/mof-capabilities.yaml` plus `mof-model-change` /
`mof-state-bridge-audit`. External adapter health is reported by `doctor`; a missing optional
adapter is not a reason to bypass C2G/OMO/GaC.

## Closeout

When the task is complete:

```bash
uv run --with pyyaml python bin/agent-workflow.py observe "<run-id>"
uv run --with pyyaml python bin/agent-workflow.py handoff "<run-id>"
uv run --with pyyaml python bin/agent-workflow.py close "<run-id>" \
  --status ok \
  --evidence "<verification command or artifact>"
```

Do not create git commits unless the user explicitly requested commits.
