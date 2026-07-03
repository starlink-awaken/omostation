# CLAUDE.md — omostation AI Context Loader

> 最后更新: 2026-07-02
> Purpose: session startup protocol for AI agents.
> Detailed engineering rules live in [`AGENTS.md`](AGENTS.md).
> Stable architecture contracts live in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## 0. Startup Protocol

> [!IMPORTANT]
> **KOS (Knowledge Operating System) Hardware Cold-Start Protocol**
> You are equipped with `mcp-server-kos` as your external read-only hard drive.
> To align your mental model and avoid historical architectural regressions, you MUST run the following KOS query sequence during your first turn:
>
> 1. **Query Current Decisions & Goals**:
>    `mcp-server-kos::query_custom_sql(sql="SELECT doc_id, title, canonical_path FROM documents WHERE canonical_path LIKE '%BRIEF.md%' LIMIT 1")`
>    Read the resulting BRIEF.md file path. It contains the active technical debts (needs-human) and X3 metrics.
> 2. **Traverse ADR Decisions**:
>    `mcp-server-kos::search_kos(query="ADR-012")`
>    Pay close attention to ADR-0124 (retrospective S1) and ADR-0125 (S2 retrospective).
> 3. **Identify Domain Schemas**:
>    `mcp-server-kos::list_entities(limit=50)`

Before changing code or governed state, load the current context:

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap
uv run --with "pyyaml" python "bin/agent-workflow.py" status --json
```

If task-specific runtime facts are needed, read the SSOT files reported by `bootstrap` instead of copying values into this document. If MCP context is available, prefer the cockpit workspace-context tool.

Do not copy values from those files into this document. They are runtime facts and drift quickly.

## 0.5 P74 Workflow Solidification Check (ADR-0130)

After bootstrap, every agent MUST verify P74 health. P74 is the常态化 mechanism
(常态化机制) for agent-workflow silence detection — see `.omo/_knowledge/decisions/0130-p74-workflow-solidification.md`.

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" compliance --json
```

Read `.p74_solidification.warn_count`:

- `0`: continue
- `> 0` (excluding `handoff-resume` / `observer-audit`): treat as governance signal.
  Read `.omo/standards/p74-solidification-contract.md` §3 decision tree for actions.
  If workflow has neither `has_recent_run` nor `has_check_coverage`, register it via
  `agent-workflows.yaml::diff_checks` or `silent_workflow_policy.excluded_workflows`.

The `silent_workflow_policy` field in `agent-workflows.yaml` is the SSOT for
silent workflow classification. Do not invent categories — extend this list.

## 1. Session Role

`CLAUDE.md` is the lightweight context loader. It should answer only:

- What must be read first?
- Which files are authoritative?
- Which operations are unsafe without a broker or explicit user request?
- Where should deeper guidance be found?

It should not duplicate project tables, architecture diagrams, historical closeout reports, rule registries, test counts, port values, or generated snapshots.

## 2. Mandatory Boundaries

The authoritative SSOT map (all fact types and their sources) lives in [`ARCHITECTURE.md` §1](ARCHITECTURE.md). The table below lists only the boundaries most relevant to session startup.

| Topic | Rule | Read More |
|------|------|-----------|
| Runtime state | Read from `.omo/state/system.yaml`; do not hard-code | [`ARCHITECTURE.md` §1](ARCHITECTURE.md) |
| Runtime projection refresh | Use `uv run --project projects/omo omo state sync`; do not run ad-hoc generator scripts from hooks | [`.omo/_knowledge/decisions/0128-state-generation-concurrency.md`](.omo/_knowledge/decisions/0128-state-generation-concurrency.md) |
| Governed `.omo/` writes | Use `omo` CLI/MCP or approved broker, not ad-hoc file I/O | [`projects/omo/CLAUDE.md`](projects/omo/CLAUDE.md) |
| Ports | Read and register through `protocols/port-registry.yaml` | [`ARCHITECTURE.md` §1](ARCHITECTURE.md) |
| Vault paths | Read from `protocols/vault-paths.yaml`; do not hard-code `~/Documents/` paths | [`ARCHITECTURE.md` §1](ARCHITECTURE.md) |
| Project metadata | Read from `docs/project-registry.yaml` | [`docs/project-registry.yaml`](docs/project-registry.yaml) |
| Agent workflows | Use `bin/agent-workflow.py`; do not rely on prompt memory alone | [`.omo/standards/agent-workflow-contract.md`](.omo/standards/agent-workflow-contract.md) |

## 3. Working Discipline

1. For work with more than a couple of steps, keep a visible todo list.
2. Read the target project `AGENTS.md` / `CLAUDE.md` before editing that project.
3. Use `rg` for text discovery and project-specific tools for code discovery when available.
4. Use the available file-editing tools (Edit, Create, MultiEdit, or `apply_patch`) for manual edits.
5. Do not delete, reset, move, commit, or push unless explicitly confirmed. See [`AGENTS.md` §6](AGENTS.md#6-git-and-submodules) for the full git and submodule policy.
6. If a governance protocol demands a commit but the current user/session policy does not authorize one, finish the working-tree changes, report the exact files, and ask for explicit commit confirmation.

## 4. Common Commands

```bash
make gac-local-gate
uv run --with "pyyaml" python "bin/agent-workflow.py" list
uv run --with "pyyaml" python "bin/agent-workflow.py" agents
uv run --with "pyyaml" python "bin/agent-workflow.py" integrations
uv run --with "pyyaml" python "bin/agent-workflow.py" adapters
uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap
uv run --with "pyyaml" python "bin/agent-workflow.py" status --json
uv run --project "projects/omo" omo state sync --dry-run --json
uv run --project "projects/omo" omo state sync --json
uv run --with "pyyaml" python "bin/agent-workflow.py" start <workflow-id> --profile <agent-profile> --objective "<summary>"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> --path <path>
uv run --with "pyyaml" python "bin/agent-workflow.py" verify <run-id> --from-diff --execute
uv run --with "pyyaml" python "bin/agent-workflow.py" closeout <run-id>
uv run --with "pyyaml" python "bin/agent-workflow.py" compliance <run-id>
uv run --with "pyyaml" python "bin/agent-workflow.py" doctor
uv run --with "pyyaml" python "bin/gac-local-gate.py" --scope files --file <path> --json
uv run --with "pyyaml" python "bin/doc-ssot-lint.py" --json
uv run --with "pyyaml" python "bin/ssot-guardian.py"
bash "tests/integration/run-all.sh"
cd "projects/kairon" && make test-diff
cd "projects/gbrain" && bun test
```

## 5. Routing Hints

| Need | Route |
|------|-------|
| Workspace architecture | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Layer/project placement | [`LAYER-INDEX.md`](LAYER-INDEX.md) |
| Agent development rules | [`AGENTS.md`](AGENTS.md) |
| Project metadata | [`docs/project-registry.yaml`](docs/project-registry.yaml) |
| System panorama & BOS routing | [`docs/PANORAMA.md`](docs/PANORAMA.md) |
| Architecture deep-dive | [`docs/ARCHITECTURE-DETAILED-MAP.md`](docs/ARCHITECTURE-DETAILED-MAP.md) |
| Functional capability map | [`docs/FUNCTIONAL-CAPABILITY-MAP.md`](docs/FUNCTIONAL-CAPABILITY-MAP.md) |
| Agora callchain | [`docs/I0-AGORA-CALLCHAIN.md`](docs/I0-AGORA-CALLCHAIN.md) |
| Vision & roadmap | [`docs/VISION-ROADMAP.md`](docs/VISION-ROADMAP.md) |
| OMO governance kernel rules | [`projects/omo/CLAUDE.md`](projects/omo/CLAUDE.md) |
| Executable agent workflows | [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) |
| AGCP status/scoped gate/claim policy | [`.omo/standards/agent-workflow-contract.md`](.omo/standards/agent-workflow-contract.md) |
| Internal integration contracts | `uv run --with "pyyaml" python "bin/agent-workflow.py" integrations` |
| MOF capabilities | [`.omo/_truth/registry/mof-capabilities.yaml`](.omo/_truth/registry/mof-capabilities.yaml) |
| External adapter contracts | `uv run --with "pyyaml" python "bin/agent-workflow.py" adapters` |
| External adapter health | `uv run --with "pyyaml" python "bin/agent-workflow.py" doctor` |
| L0/SSOT/M0/MOF 对齐审计 | [`.omo/_knowledge/audits/2026-06-29-l0-ssot-m0-mof-alignment.md`](.omo/_knowledge/audits/2026-06-29-l0-ssot-m0-mof-alignment.md) (D1-D6 drift + 四者关系图) |

## 6. Closeout

```bash
git status --short
make gac-local-gate
uv run --with "pyyaml" python "bin/ssot-guardian.py"
```

Run broader tests only when the edited surface warrants them. Documentation-only changes usually need the documentation SSOT check plus a clear diff review. For the full closeout checklist (including reporting files changed and checks skipped), see [`AGENTS.md` §9](AGENTS.md#9-closeout-checklist).
