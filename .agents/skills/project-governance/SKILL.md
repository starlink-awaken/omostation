---
name: project-governance
description: Use when an agent changes this workspace or a child project and needs executable governance workflow routing instead of relying on AGENTS.md or CLAUDE.md memory.
---

# Project Governance Workflow

This skill is a thin bootloader. The source of truth is:

- Registry: `.omo/_truth/registry/agent-workflows.yaml`
- Runner: `bin/agent-workflow.py`
- Contract: `.omo/standards/agent-workflow-contract.md`
- Governance evolution roadmap: `.omo/_truth/registry/governance-evolution-roadmap.yaml`

## Required First Step

Run the bootstrap before making changes. It includes lint, workflow/profile summaries,
integration contracts, adapter contracts, health summaries, and next commands.

```bash
uv run --with pyyaml python bin/agent-workflow.py bootstrap
# or through the L3 entry:
uv run --project projects/cockpit cockpit agent
```

## Choose A Workflow

List the available workflows:

```bash
uv run --with pyyaml python bin/agent-workflow.py list
uv run --with pyyaml python bin/agent-workflow.py agents
uv run --with pyyaml python bin/agent-workflow.py integrations
uv run --with pyyaml python bin/agent-workflow.py adapters
uv run --with pyyaml python bin/agent-workflow.py status --json
uv run --with pyyaml python bin/agent-workflow.py compliance
uv run --with pyyaml python bin/governance-evolution.py status --json
uv run --with pyyaml python bin/governance-evolution.py validate --json
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

## Governance Evolution

Use the evolution runner when the task asks what the system still needs, whether governance
capabilities have drifted, or how AGCP, OMO, C2G, MOF, BOS, and Cockpit connect.
`validate` checks the roadmap shape and the Agora `bos://governance/evolution/*` route alignment.

```bash
uv run --with pyyaml python bin/governance-evolution.py status --json
uv run --with pyyaml python bin/governance-evolution.py traces --json
uv run --with pyyaml python bin/governance-evolution.py golden-paths --json
uv run --with pyyaml python bin/governance-evolution.py packages --json
uv run --with pyyaml python bin/governance-evolution.py packages --decisions <file> --json
uv run --with pyyaml python bin/governance-evolution.py packages --decisions <file> --require-ready --json
uv run --project projects/cockpit cockpit governance evolution status --json
uv run --project projects/cockpit cockpit governance evolution packages --json
uv run --project projects/cockpit cockpit governance evolution packages --decisions <file> --require-ready --json
```

`packages` reports classification health (`ok` / `unknown_count`), release readiness
(`release_ready` / `review_findings`), and actionable review routing (`review_workflows`,
`review_plan`, `owner`, `workflow`, `recommended_action`). Use `review_plan` as the batched
execution view: it groups packages by workflow, profile, owners, paths, start command,
claim commands, closeout template, and include/exclude/defer decision options.
Use `decision_template` as the path-level release checklist: every review-required path starts
with `decision: null` and must be marked include, exclude, or defer by the responsible workflow.
Pass a filled decision file back through `packages --decisions <file> --json` before release;
the runner reports invalid, pending, and ready counts without writing governed state.
Use `--require-ready` for blocking release gates; it returns non-zero until all current review
decisions are valid and complete.
Runtime/data outputs, submodule pointers, OMO task lifecycle artifacts, root governance audit
reports, and workspace config/CI workflow changes should be reviewed or excluded before packaging
through the reported workflow.

Do not copy initiative lists into AGENTS.md, CLAUDE.md, or this skill. The roadmap registry is
the machine SSOT, and `docs/GOVERNANCE-EVOLUTION-ROADMAP.md` is only the human navigation page.

## Start Or Resume

For any multi-step task, create a run record before editing:

```bash
uv run --with pyyaml python bin/agent-workflow.py start project-doc-change \
  --actor "${USER:-agent}" \
  --profile governance-agent \
  --objective "<short objective>"

uv run --with pyyaml python bin/agent-workflow.py claim "<run-id>" \
  --path "<path-or-directory>"
```

`claim_policy` is owned by `.omo/_truth/registry/agent-workflows.yaml`. It is tiered:
core governance paths can be `required`, while broader docs and entrypoint paths remain
`advisory`. `verify`, `closeout`, and `status` report claim coverage; required misses block
the run until the current run claims the file.

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

uv run --with pyyaml python bin/agent-workflow.py verify "<run-id>" \
  --from-diff \
  --execute

uv run --with pyyaml python bin/gac-local-gate.py --scope files --file "<path>" --json
```

Manual commands in the registry are intentional handoffs to the agent or the project-local docs. Do not pretend they ran.

## External Adapters

Check optional tool availability:

```bash
uv run --with pyyaml python bin/agent-workflow.py doctor
uv run --with pyyaml python bin/agent-workflow.py observe
uv run --with pyyaml python bin/agent-workflow.py status --health
```

`adapters` is the contract view: it declares each external tool's authority, ingress workflow,
SSOT rule, bridge command, and fallback. `doctor` is the health view.
`integrations` is the internal contract view for GaC, OMO, C2G, Cockpit, and MOF.

`bmad` and `openspec` are routed through C2G/OMO bridge commands when source files exist. `gstack` and `beads` are optional adapters and must degrade to advisory mode when missing.
MOF changes use `.omo/_truth/registry/mof-capabilities.yaml` plus `mof-model-change` /
`mof-state-bridge-audit`. External adapter health is reported by `doctor`; a missing optional
adapter is not a reason to bypass C2G/OMO/GaC.

## Closeout

When the task is complete:

```bash
uv run --with pyyaml python bin/agent-workflow.py closeout "<run-id>" \
  --evidence "<verification command or artifact>"

uv run --with pyyaml python bin/agent-workflow.py compliance "<run-id>"
```

Do not create git commits unless the user explicitly requested commits.
