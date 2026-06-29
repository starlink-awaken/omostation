---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-29
---

# Agent Workflow Contract

> Scope: executable project-level workflows for human-operated and autonomous agents.
> SSOT: `.omo/_truth/registry/agent-workflows.yaml`.

## 1. Purpose

`AGENTS.md` and `CLAUDE.md` are startup indexes, not enforcement layers. Agents can forget prompt context after compression, and different runtimes obey instructions differently.

The durable contract is:

1. Declarative workflow registry.
2. Executable runner.
3. Resumable run records.
4. GAC/OMO/C2G/Cockpit gates and brokers.

## 2. Layering

| Layer | Artifact | Role |
|-------|----------|------|
| SSOT | `.omo/_truth/registry/agent-workflows.yaml` | Workflow definitions, lanes, locks, stages, external adapters |
| Runner | `bin/agent-workflow.py` | Lint, plan, execute stages, start/resume/close runs |
| Skill | `.agents/skills/project-governance/SKILL.md` | Thin bootloader for agent runtimes |
| Gate | `make gac-local-gate` | Local enforcement through GAC and SSOT checks |
| Broker | `projects/omo` / `projects/c2g` | Governed state mutation and external spec ingress |
| L3 Entry | `projects/cockpit` | Human-facing compass/workflow entry for C2G and orchestration |

## 3. Required Behavior

Before a multi-step agent task:

```bash
uv run --with pyyaml python bin/agent-workflow.py lint
uv run --with pyyaml python bin/agent-workflow.py start <workflow-id> --objective "<summary>"
```

After compression or handoff:

```bash
uv run --with pyyaml python bin/agent-workflow.py resume <run-id>
uv run --with pyyaml python bin/agent-workflow.py handoff <run-id>
```

Before closeout:

```bash
uv run --with pyyaml python bin/agent-workflow.py run <workflow-id> --stage verification --execute
uv run --with pyyaml python bin/agent-workflow.py handoff <run-id>
uv run --with pyyaml python bin/agent-workflow.py close <run-id> --status ok --evidence "<checks>"
```

Manual stage entries are not optional checks. They represent work that cannot be safely generalized, such as project-local tests or a broker-specific mutation.

## 4. Concurrency

Workflow runs create lock records under `.omo/_delivery/agent-workflows/locks`. A lock represents a governance surface, not a process mutex. Agents must treat an existing lock as a stop-and-inspect signal unless the user explicitly authorizes takeover.

Recommended lock scopes:

- `project:<name>` for project-local edits.
- `.omo` for state-plane changes.
- `spaces` for tenant-space manifests.
- `root-gitlinks` for submodule pointer closeout.
- `doc-ssot` for broad documentation rewrites.

## 5. External Tool Adapters

External systems are patterns, not new authorities:

| Tool | Integration Rule |
|------|------------------|
| Superpowers | Skill-first discipline maps to project-governance skill and workflow checklist. |
| BMAD | Specs enter governance through the OMO bridge compatibility path. |
| OpenSpec | Specs enter governance through the OMO bridge compatibility path. |
| GStack | Memory/learnings/handoff evidence may enrich resume state when installed. |
| beads | Dependency-tracked work items may be imported as OMO planned tasks when installed. |

If an adapter is missing, `bin/agent-workflow.py doctor` reports advisory status. Missing optional adapters must not block unrelated governance workflows.

Current ingress routing:

- Pitch files should use `uv run --project projects/cockpit cockpit compass bet <pitch.md>` or the underlying `uv run --project projects/c2g c2g bet <pitch.md>`.
- BMAD/OpenSpec files currently use the compatibility bridge `uv run --project projects/omo omo bridge --format <bmad|openspec> <source-file>` until the Cockpit/C2G path fully replaces it.

## 6. Non-Goals

- Do not copy all GAC rules into skills or docs.
- Do not create a second task system beside OMO/C2G.
- Do not bypass OMO/C2G brokers for task, debt, goal, or state-plane truth mutations.
- Do not rely on agent personality or model type for enforcement.

## 7. Drift Control

The workflow registry is validated by:

```bash
uv run --with pyyaml python bin/agent-workflow.py lint
make gac-local-gate
```

Any new workflow must include:

- `id`, `title`, `purpose`.
- `allowed_lanes`.
- `lock_scopes`.
- `surfaces.read` and `surfaces.write`.
- Four phases: `preflight`, `execute`, `verification`, `closeout`.
- Command entries with `id`, `mode`, and list-form `command`.
