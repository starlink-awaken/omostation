# AGENTS.md — projects/ Directory Guide

> Scope: the `projects/` container and its child repositories.
> Workspace-wide rules are in [`../AGENTS.md`](../AGENTS.md).

## 1. Boundary

`projects/` is a container for independently owned project repositories. It is not a single build unit and should not grow root-level build configuration unless the workspace architecture explicitly changes.

Facts such as project count, layer, package count, versions, and roles are owned by [`../docs/project-registry.yaml`](../docs/project-registry.yaml). This file only explains how to work inside the container.

## 2. Before Editing A Project

1. Read [`../AGENTS.md`](../AGENTS.md).
2. Read the target project `AGENTS.md` and `CLAUDE.md` when present.
3. Check `git status --short` at the workspace root and inside the target project.
4. For multi-step work, run `uv run --with "pyyaml" python "../bin/agent-workflow.py" bootstrap`, check `status`, create a run with `start`, then claim the project path with `uv run --with "pyyaml" python "../bin/agent-workflow.py" claim <run-id> --path projects/<project>`.
5. Identify whether the target is a submodule or a normal directory.
6. Use the project-local build and test commands.

## 3. Layer Placement

Use [`../LAYER-INDEX.md`](../LAYER-INDEX.md) for the human-readable layer map, [`../docs/project-registry.yaml`](../docs/project-registry.yaml) for machine-readable metadata, and [`../docs/generated/project-layer-index.md`](../docs/generated/project-layer-index.md) for the generated layer digest.

## 4. Common Workflows

### Python Projects

```bash
cd "projects/<project>"
uv sync
uv run pytest "tests/" -q
uv run ruff check "."
uv run ruff format "."
```

Some projects expose Makefile targets. Prefer local documented targets when they exist.

### kairon

```bash
cd "projects/kairon"
make test-diff
make lint
```

### gbrain

```bash
cd "projects/gbrain"
bun install
bun test
bun run ci:local
```

### Frontend Projects

```bash
cd "projects/<frontend-project>"
bun install
bun run build
bun run lint
```

## 5. Submodule Discipline

- Most child directories are independent repositories.
- Do not commit inside a submodule unless the user explicitly asked for commits.
- If a submodule changes and commits are requested, commit inside the submodule first, then update the root pointer.
- Do not chase unrelated dirty submodule pointers. Report them when they affect the requested work.
- Do not edit archived snapshots unless the task explicitly targets archive maintenance.

## 6. Governed State

`projects/.omo` is a symlink to the workspace governance state. Do not edit it directly. Use OMO/C2G broker paths described in:

- [`../AGENTS.md`](../AGENTS.md)
- [`omo/CLAUDE.md`](omo/CLAUDE.md)
- [`c2g/CLAUDE.md`](c2g/CLAUDE.md)

## 7. Code Organization Patterns

Most Python projects follow:

```
<project>/
├── src/<package_name>/
├── tests/
├── pyproject.toml
├── uv.lock
├── README.md
├── AGENTS.md
└── CLAUDE.md
```

Monorepos such as `kairon` and `aetherforge` have package-specific layouts. Read their project docs before assuming paths.

## 8. Testing Strategy

- Prefer targeted tests for narrow edits.
- Use integration smoke only when a change touches cross-project behavior.
- For docs-only edits inside `projects/`, run the workspace documentation SSOT check from the root:

```bash
cd ".."
uv run --with "pyyaml" python "bin/doc-ssot-lint.py" --json
```

## 9. Gotchas

- There is no universal `projects/` test command.
- Python projects generally use `uv`; TypeScript projects generally use Bun.
- Some tests require local services or containers. Check project docs before treating failures as code regressions.
- Root `.omo/` state is governed; direct writes create drift.
- Avoid copying workspace architecture tables into project docs. Link to root architecture instead.

## 10. Closeout

From the workspace root:

```bash
git status --short
uv run --with "pyyaml" python "bin/agent-workflow.py" status --json
uv run --with "pyyaml" python "bin/agent-workflow.py" lint
uv run --with "pyyaml" python "bin/agent-workflow.py" closeout <run-id>
uv run --with "pyyaml" python "bin/agent-workflow.py" compliance <run-id>
uv run --with "pyyaml" python "bin/doc-ssot-lint.py" --json
```

Then report touched projects, verification run, and any unresolved dirty state that predated your work.
