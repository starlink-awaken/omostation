---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-07-15
type: ssot
---

# Agent Workflow Contract

> Scope: executable project-level workflows for human-operated and autonomous agents.
> SSOT: `.omo/_truth/registry/agent-workflows/`.
> Compatibility only: `.omo/_truth/registry/agent-workflows.yaml` is a generated read-only projection.
> Mandatory delivery rule: **ADR-0203** / `requirement_iteration_policy` (mode: required).

## 1. Purpose

`AGENTS.md` and `CLAUDE.md` are startup indexes, not enforcement layers. Agents can forget prompt context after compression, and different runtimes obey instructions differently.

The durable contract is:

1. Declarative workflow registry.
2. Executable runner.
3. Resumable run records.
4. GAC/OMO/C2G/Cockpit gates and brokers.
5. **Requirement iterations always start a workflow run** (ADR-0203) — not optional prompt etiquette.

## 2. Layering

| Layer | Artifact | Role |
|-------|----------|------|
| SSOT | `.omo/_truth/registry/agent-workflows/` | Canonical workflow definitions, lanes, locks, stages, profiles, and adapters |
| Agent Profiles | `.omo/_truth/registry/agent-workflows/profiles/` | Machine-readable agent roles, workflow allowlists, lane boundaries |
| Internal Integrations | `.omo/_truth/registry/agent-workflows/_root.yaml::internal_integrations` | Machine-readable contracts for GaC, OMO, C2G, Cockpit, and MOF |
| Legacy projection | `.omo/_truth/registry/agent-workflows.yaml` | Generated read-only compatibility view; never a writer authority |
| Runner | `bin/agent-workflow.py` | Lint, status, plan, claim, verify, closeout, compliance, and run state |
| Skill | `.agents/skills/project-governance/SKILL.md` | Thin bootloader for agent runtimes |
| Gate | `make gac-local-gate` | Local enforcement through GAC, adapter, MOF, and SSOT checks |
| Broker | `projects/omo` / `projects/c2g` | Governed state mutation and external spec ingress |
| MOF | `.omo/_truth/registry/mof-capabilities.yaml` | M1/M2/M3 model tool registry and schema/state bridge checks |
| L3 Entry | `projects/cockpit` | Human-facing compass and `cockpit agent` entry for C2G and agent governance |

## 3. Required Behavior

### 3.1 Requirement iteration is mandatory (ADR-0203)

SSOT: `agent-workflows/_root.yaml::requirement_iteration_policy` (`mode: required`).

**Definition — requirement iteration** includes any delivery that changes the workspace for a
feature, bugfix, ops landing, governance/SSOT/ADR/contract edit, or submodule pointer closeout
tied to that delivery. **Not** pure read-only Q&A/explore.

**Mandatory lifecycle** (skip = non-compliant for all agent runtimes):

```text
bootstrap → status → start → claim → edit/test → verify → closeout
```

| Allowed without a run | Forbidden without a run |
|----------------------|-------------------------|
| Pure read-only answers | Code/docs/governance edits that implement a需求 |
| `observer-audit` (read-only) | "I'll just open a PR then start workflow later" |
| Explicit user waiver (record in closeout) | Completing work with no `run-id` / no ledger events |

**Waiver evidence template**: [`docs/operations/workflow-waiver-template.md`](../../docs/operations/workflow-waiver-template.md).  
Agents must not invent waivers. Gate bypass (`AGCP_REQUIREMENT_ITERATION_GATE=0`) requires the same evidence block.

**Workflow selection**: before `start`, prefer  
`agent-workflow suggest --from-diff --profile <agent-profile>` when a diff exists  
(reduces P74 “wrong generic workflow” drift).

`handoff-resume` recovers an **existing** run; it does not authorize untracked edits.

P74 (`silent_workflow_policy`) is complementary: it catches registered workflows that go unused.
ADR-0203 catches **delivery work that bypasses workflow entirely**.

### 3.2 Start sequence

Before a requirement iteration (or any multi-step agent task that writes):

```bash
uv run --with pyyaml python bin/agent-workflow.py bootstrap
uv run --with pyyaml python bin/agent-workflow.py status --json
uv run --with pyyaml python bin/agent-workflow.py start <workflow-id> \
  --profile <agent-profile> \
  --objective "<summary>"
uv run --with pyyaml python bin/gac/affected-graph.py \
  --workspace-root . \
  --changed-projects workspace-root <project-name> \
  --output .omo/evidence/<session>/affected-graph-receipt.json --json
uv run --with pyyaml python bin/agent-workflow.py claim <run-id> \
  --path <path> \
  --affected-receipt .omo/evidence/<session>/affected-graph-receipt.json
```

Agent roles must be selected from `agent_profiles`. Workflow lint fails when a workflow references
an unknown role or a role that has not allowlisted the workflow. `start` requires `--profile` for
all profiled workflows, and the run record persists that profile for compressed-session recovery.

`bootstrap` is the single startup entrypoint. It reports lint status, workflows, profiles, internal
integrations, external adapters, health summaries, and next commands without requiring an agent to
remember several separate discovery commands.

`status` is the steady-state entrypoint. It reports active and closed runs, lock count, stale locks,
last verify/closeout events, compliance SLO, staged lane status, claim coverage, and the recommended
next action. `--health` adds doctor checks when a heavier health read is useful.

`claim` is the path/surface-level concurrency step. It adds path or governance-surface locks to
the active run and records an `agent_workflow_claim` ledger event. Broad workflow locks are still
created by `start`; `claim` narrows the edit surface for multi-agent work. The registry-owned
`claim_policy` starts in `advisory` mode: verify, closeout, and status warn on unclaimed governed
paths without hard failing. If the policy is raised to `required`, the same check becomes blocking.

Every write claim must reference an `affected-graph-receipt/v1` JSON document. The receipt binds
sorted `changed_projects` and `affected_projects` to the SHA-256 digest of
`docs/layer-contract.yaml`; `receipt_hash` is SHA-256 over canonical JSON for the other receipt
fields. Before acquiring a path lock, OMO recalculates both hashes and the affected graph, rejects
unknown projects, and verifies that every `projects/<name>/...` claim is covered by
`affected_projects`. Root repository paths, including `docs/`, are represented explicitly by the
reserved project name `workspace-root`; they are never silently dropped from the graph.

`--affected-hash` remains only as a deprecated CLI alias for a receipt **file path** during client
migration. A bare hash, dummy string, missing file, tampered receipt, stale layer-contract digest,
or receipt that omits a claimed project is invalid and must fail before lock acquisition.
Receipt references must be canonical workspace-relative paths to regular files inside the workspace;
absolute paths, traversal, symlinks, and external files are rejected so local machine paths never
enter run or ledger state. The broad path `projects` is ambiguous and rejected. Any non-empty
`--surface` claim requires `workspace-root` in the receipt. The root producer publishes a receipt
atomically and exclusively and refuses to overwrite existing evidence.

After compression or handoff:

```bash
uv run --with pyyaml python bin/agent-workflow.py resume <run-id>
uv run --with pyyaml python bin/agent-workflow.py handoff <run-id>
```

Before closeout:

```bash
uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute
uv run --with pyyaml python bin/agent-workflow.py closeout <run-id> --evidence "<checks>"
uv run --with pyyaml python bin/agent-workflow.py compliance <run-id>
```

Manual stage entries are not optional checks. They represent work that cannot be safely generalized, such as project-local tests or a broker-specific mutation.

`close` remains a low-level primitive. Normal agent closeout should use `closeout`, which runs
diff-aware verification, observes locks/ledger consistency, records closeout evidence, and releases
locks in one path.

Vision→BET→retro bind (BET-Y1Q1-T6-02): `start --bet` persists `bet_id` on the run record.
`ok` closeout and `bet-ledger complete` call `bin/plan/chain-bind-check.py`. Pointers only:
`redlines.yaml::vision-to-retro-chain`, `docs/architecture/wave-gate-bet-map.md`.

## 4. Concurrency

Workflow runs create lock records under `.omo/_delivery/agent-workflows/locks`. A lock represents a governance surface, not a process mutex. Agents must treat an existing lock as a stop-and-inspect signal unless the user explicitly authorizes takeover.

Observer audits are read-only:

```bash
uv run --with pyyaml python bin/agent-workflow.py observe
uv run --with pyyaml python bin/agent-workflow.py observe <run-id>
```

The observer decision is `continue`, `halt`, or `escalate`. It halts on orphan locks, malformed lock files, closed runs that still hold locks, or active runs missing expected locks. It escalates on expired locks.

Recommended lock scopes:

- `project:<name>` for project-local edits.
- `.omo` for state-plane changes.
- `spaces` for tenant-space manifests.
- `root-gitlinks` for submodule pointer closeout.
- `doc-ssot` for broad documentation rewrites.
- `path:<repo-path>` for claimed edit paths.
- `surface:<name>` for claimed governance surfaces.

## 5. Diff-Aware Verification And Evidence

`diff_checks` in `.omo/_truth/registry/agent-workflows/_root.yaml` maps file patterns to required
verification commands. Agents can inspect the selected checks without side effects:

```bash
uv run --with pyyaml python bin/agent-workflow.py verify --file bin/agent-workflow.py
```

For real closeout, agents should run:

```bash
uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute
```

Verification writes `agent_workflow_verify` events to the ledger when a run id is provided. The
evidence schema in the registry defines required ledger fields and command-result fields.

When `agent-workflow verify --execute` runs a selected check, it passes the selected file set through
`AGENT_WORKFLOW_MATCHED_FILES`. `gac-local-gate.py` uses that scoped file set for its change-lane
subcheck while keeping direct `make gac-local-gate` behavior staged and global. This keeps run-scoped
verification useful in multi-agent worktrees without weakening the full local gate.

For direct CLI use, the same gate exposes explicit scope:

```bash
uv run --with pyyaml python bin/gac/gac-local-gate.py --scope staged --json
uv run --with pyyaml python bin/gac/gac-local-gate.py --scope files --file bin/agent-workflow.py --json
uv run --with pyyaml python bin/gac/gac-local-gate.py --scope run --run-id <run-id> --json
```

`compliance` audits run records, locks, ledger parseability, closed-run evidence, verify events,
and closeout usage. Warnings are allowed for historical runs, but halt findings indicate the
control plane cannot prove the run is governed.

## 6. Internal Integrations

Internal integrations use the same contract pattern as external adapters. Each integration must
declare `status`, `authority`, `owner`, `ssot_rule`, `health_command`, and `health_required`.
`agent-workflow integrations` exposes this map, and `make gac-local-gate` verifies it.

## 7. External Tool Adapters

External systems are patterns, not new authorities:

| Tool | Integration Rule |
|------|------------------|
| Superpowers | Skill-first discipline maps to project-governance skill and workflow checklist. |
| BMAD | Specs enter governance through the OMO bridge compatibility path. |
| OpenSpec | Specs enter governance through the OMO bridge compatibility path. |
| GStack | Memory/learnings/handoff evidence may enrich resume state when installed. |
| beads | Dependency-tracked work items may be imported as OMO planned tasks when installed. |

Every external adapter must declare `authority`, `ssot_rule`, and `ingress_workflow` under
`.omo/_truth/registry/agent-workflows/adapters/`. `agent-workflow lint` enforces these fields, and
`agent-workflow adapters` exposes them for agents that cannot retain prompt context.
`make gac-local-gate` runs both the adapter contract view and adapter health doctor.

If an adapter is missing or not initialized in the current workspace, `bin/agent-workflow.py doctor`
reports advisory health. Missing optional adapters must not block unrelated governance workflows.

Current ingress routing:

- Pitch files should use `uv run --project projects/cockpit cockpit compass bet <pitch.md>` or the underlying `uv run --project projects/c2g c2g bet <pitch.md>`.
- BMAD/OpenSpec files currently use the compatibility bridge `uv run --project projects/omo omo bridge --format <bmad|openspec> <source-file>` until the Cockpit/C2G path fully replaces it.
- beads items should be imported into C2G/OMO rather than treated as a second task SSOT.
- gstack memory should enrich `handoff-resume`; when gstack is absent, the agent workflow handoff is canonical.

## 8. MOF Coverage

MOF is a first-class workflow surface:

- `mof-model-change` covers M1/M2/M3 model edits, schema validation, state bridge reporting, drift checks, and MOF version evidence.
- `mof-state-bridge-audit` is the read-only check path for OMO task alignment and MOF schema health.
- `make gac-local-gate` includes MOF schema validation, MOF state bridge reporting, and MOF drift detection.

## 9. Cockpit Entry

Cockpit exposes the same runner instead of reimplementing governance logic:

```bash
uv run --project projects/cockpit cockpit agent
uv run --project projects/cockpit cockpit agent bootstrap --skip-health
uv run --project projects/cockpit cockpit agent status --json
uv run --project projects/cockpit cockpit agent verify <run-id> --from-diff --execute
uv run --project projects/cockpit cockpit agent closeout <run-id>
```

`cockpit agent-workflow` remains as a compatibility alias.

## 10. State Sync Workflow

High-churn runtime projections use a single workflow and broker:

```bash
uv run --with pyyaml python bin/agent-workflow.py run state-sync --stage preflight --execute
uv run --with pyyaml python bin/agent-workflow.py run state-sync --stage execute --execute
uv run --project projects/omo omo state sync --dry-run --json
uv run --project projects/omo omo state sync --json
```

`post-commit` hooks and WatchPaths emit `state_stale` events through `bin/gac/state-stale-emit.py`.
They must not directly run `compass_radar.py`, `generate-brief.py`, or governance-data generators.
The registered mutation surface is `omo-state-sync-projection`, and its broker is
`projects/omo/src/omo/omo_ingress_state.py:sync_state_projection`.

The broker owns content fingerprinting, process locking, runtime delivery evidence, and mutation
ledger records for `.omo/state/health.yaml`, `.omo/state/system.yaml`, `BRIEF.md`, and
`.omo/_control/governance-data.json`. Agents should use the workflow or the `omo state sync`
CLI instead of hand-editing those projections.

## 11. Non-Goals

- Do not copy all GAC rules into skills or docs.
- Do not create a second task system beside OMO/C2G.
- Do not bypass OMO/C2G brokers for task, debt, goal, or state-plane truth mutations.
- Do not rely on agent personality or model type for enforcement.

## 12. Drift Control

The workflow registry is validated by:

```bash
uv run --with pyyaml python bin/agent-workflow.py lint
uv run --with pyyaml python bin/agent-workflow.py doctor
make gac-local-gate
```

`lint` and `doctor` also check AGCP drift across the workflow registry, agent CLI registry,
Cockpit entrypoint, Agora BOS route family, and MOF M1 Workflow/BOSRoute nodes. MOF model paths
must continue to trigger MOF schema, state-bridge, and drift diff checks.

Any new workflow must include:

- `id`, `title`, `purpose`.
- `allowed_lanes`.
- `lock_scopes`.
- `surfaces.read` and `surfaces.write`.
- Four phases: `preflight`, `execute`, `verification`, `closeout`.
- Command entries with `id`, `mode`, and list-form `command`.
- Referenced `agents.roles` must exist in `agent_profiles`.

Any new diff-aware check must include:

- `id`.
- `paths` or `always: true`.
- list-form `command`.
- boolean `required` when it is explicitly set.
