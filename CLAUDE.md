# CLAUDE.md — omostation AI Context Loader

> Purpose: session startup protocol for AI agents.
> Detailed engineering rules live in [`AGENTS.md`](AGENTS.md).
> Stable architecture contracts live in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## 0. Startup Protocol

Before changing code or governed state, load the current context:

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" lint
sed -n '1,220p' ".omo/state/system.yaml"
sed -n '1,220p' ".omo/goals/current.yaml"
find ".omo/tasks/active" -maxdepth 1 -type f -name "*.yaml" -print 2>/dev/null || find ".omo/tasks/planned" -maxdepth 1 -type f -name "*.yaml" -print
```

If MCP context is available, prefer the cockpit workspace-context tool. If it is not available, the files above are the fallback read path.

Do not copy values from those files into this document. They are runtime facts and drift quickly.

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
| Governed `.omo/` writes | Use `omo` CLI/MCP or approved broker, not ad-hoc file I/O | [`projects/omo/CLAUDE.md`](projects/omo/CLAUDE.md) |
| Ports | Read and register through `protocols/port-registry.yaml` | [`ARCHITECTURE.md` §1](ARCHITECTURE.md) |
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
uv run --with "pyyaml" python "bin/agent-workflow.py" doctor
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
| OMO governance kernel rules | [`projects/omo/CLAUDE.md`](projects/omo/CLAUDE.md) |
| Executable agent workflows | [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) |

## 6. Closeout

```bash
git status --short
make gac-local-gate
uv run --with "pyyaml" python "bin/ssot-guardian.py"
```

Run broader tests only when the edited surface warrants them. Documentation-only changes usually need the documentation SSOT check plus a clear diff review. For the full closeout checklist (including reporting files changed and checks skipped), see [`AGENTS.md` §9](AGENTS.md#9-closeout-checklist).
