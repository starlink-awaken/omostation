# AGENTS.md — Workspace Development Guide

> Root operating guide for AI coding agents and developers working in this workspace.
> Keep this file operational. Put runtime facts in SSOT files, not here.

## 1. Read This First

Before editing:

1. Read [`CLAUDE.md`](CLAUDE.md) for session startup context.
2. Read the target project `AGENTS.md` / `CLAUDE.md`.
3. Check the current working tree with `git status --short`.
4. For governed state, use OMO/C2G brokers instead of direct `.omo` writes.
5. For multi-file or high-risk changes, explain the edit surface before applying patches.

Project-specific instructions override this guide only within that project and only when they do not violate workspace governance.

## 2. Documentation SSOT Contract

| Document | Owns | Must Reference |
|----------|------|----------------|
| [`README.md`](README.md) | Front door and quick orientation | Architecture, registry, governance docs |
| [`CLAUDE.md`](CLAUDE.md) | AI session startup protocol | This file and target project docs |
| [`AGENTS.md`](AGENTS.md) | Workspace operating rules | SSOT registries for facts |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Stable architecture contracts | Registry files for counts and runtime values |
| [`LAYER-INDEX.md`](LAYER-INDEX.md) | Human-readable layer placement | `docs/project-registry.yaml` |
| [`docs/project-registry.yaml`](docs/project-registry.yaml) | Project metadata facts | Actual project metadata |
| [`.omo/state/system.yaml`](.omo/state/system.yaml) | Runtime state | Runtime probes and OMO state sync |

Do not hard-code current phase, health score, test counts, tool counts, service counts, source-file counts, port values, or generated rule inventories in Markdown. Use pointers.

The full documentation contract is [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md).

## 3. Architecture Summary

```
L4  Self       -> l4-kernel
L3  Entry      -> cockpit / cockpit-ui
I0  Weave      -> agora
L2  Engine     -> kairon / gbrain / omo / metaos
L1  Runtime    -> runtime
L0  Protocol   -> ecos
M0  Lifecycle  -> model-driven
X   Frameworks -> aetherforge / c2g / bus-foundation / omo-debt / observability / family-hub / spaces
```

Stable architecture details live in [`ARCHITECTURE.md`](ARCHITECTURE.md). Project metadata and counts live in [`docs/project-registry.yaml`](docs/project-registry.yaml).

## 4. Governance Boundaries

| Surface | Rule |
|---------|------|
| `.omo/` | State/evidence plane. Do not add long-lived execution logic here. |
| `projects/omo/` | Governance kernel: schema, audit, sync, broker, lint, task/debt lifecycle. |
| `projects/c2g/` | Strategy ingress: pitch/bet materialization into governed tasks. |
| `projects/ecos/` | Protocol and MOF layer. |
| `spaces/` | User/tenant-space manifests. Treat as governed configuration. |

For `.omo` or `spaces` mutations, use the registered broker/CLI path. If a task truly needs direct manual edits, call that out and keep the patch minimal.

## 5. Essential Commands

```bash
make gac-local-gate
uv run --with "pyyaml" python "bin/doc-ssot-lint.py" --json
uv run --with "pyyaml" python "bin/ssot-guardian.py"
uv run --with "pyyaml" python "bin/gac-validate.py" --gate
uv run --with "pyyaml" python "bin/gac-drift.py"
bash "tests/integration/run-all.sh"
cd "projects/kairon" && make test-diff
cd "projects/gbrain" && bun test
```

Prefer targeted checks for narrow edits. Broaden verification when the change touches shared contracts, generated registries, public entry points, or cross-project behavior.

## 6. Git And Submodules

- Do not run `git commit`, `git push`, `git reset --hard`, destructive checkout, or branch switching unless the user explicitly asked or confirmed.
- Root repository tracks submodule pointers and workspace metadata.
- Most `projects/*` directories are independent repositories. Commit inside the submodule first only when the user requested commits, then update the root pointer.
- Never revert unrelated dirty files. Treat them as user or concurrent-agent work.

## 7. Testing Guidance

| Change Surface | Minimum Verification |
|----------------|----------------------|
| Documentation only | `make gac-local-gate` and diff review |
| Root governance docs | `make gac-local-gate` plus `uv run --with "pyyaml" python "bin/ssot-guardian.py"` |
| Python code | Targeted `uv run pytest` or project Makefile target |
| kairon package | `make test-diff` from `projects/kairon` |
| gbrain | `bun test` or targeted Bun test |
| Cross-project contract | Targeted tests on every touched consumer plus relevant integration smoke |

If a test cannot run, report why and what risk remains.

## 8. Historical Patterns

Historical closeout details are useful evidence but should not be pasted into this file. Use pointers:

| Pattern | Read |
|---------|------|
| Agent mutation protocol | [`.omo/standards/agent-mutation-protocol.md`](.omo/standards/agent-mutation-protocol.md) |
| OMO governance surfaces | [`.omo/standards/omo-governance-surfaces.md`](.omo/standards/omo-governance-surfaces.md) |
| GaC North Star | [`.omo/_knowledge/gac/NORTH-STAR.md`](.omo/_knowledge/gac/NORTH-STAR.md) |
| P43 closed-loop pattern | [`.omo/_knowledge/patterns/p43-closed-loop-pattern.md`](.omo/_knowledge/patterns/p43-closed-loop-pattern.md) |

## 9. Closeout Checklist

1. Review `git diff --stat`.
2. Run the verification appropriate for the change.
3. Mention files changed and checks run.
4. Mention any checks skipped or blocked.
5. Do not create commits unless explicitly requested and confirmed.
