# Workspace Governance

This document is a navigation pointer, not a second governance source of truth.
The executable contracts and ownership registries remain authoritative.

## Authoritative Sources

- Operating rules: [`AGENTS.md`](AGENTS.md)
- AI session startup: [`CLAUDE.md`](CLAUDE.md)
- Governance checks and owners:
  [`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml)
- Document ownership and lifecycle:
  [`.omo/_truth/registry/document-governance.yaml`](.omo/_truth/registry/document-governance.yaml)
- Document contract:
  [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md)
- Agent workflow contract:
  [`.omo/standards/agent-workflow-contract.md`](.omo/standards/agent-workflow-contract.md)
- Project metadata:
  [`docs/project-registry.yaml`](docs/project-registry.yaml)

## Required Delivery Path

Requirement changes use the registered workflow lifecycle:

```text
bootstrap -> status -> start -> claim -> verify -> closeout
```

Use `bin/agent-workflow.py` and the workflow selected for the affected surface.
Project-specific guidance belongs in each project's `AGENTS.md` and `CLAUDE.md`;
workspace-wide rules must not be duplicated there.

## Governance Entry Points

- Local gate: `make gac-local-gate`
- Documentation SSOT check: `uv run --with pyyaml python bin/ssot/doc-ssot-lint.py --json`
- Document governance check: `python3 bin/ssot/doc-governance-check.py --no-new-warnings`
- Runtime projection refresh: `uv run --project projects/omo omo state sync`

Dynamic facts, generated projections, ports, test counts, and project inventories
must be read from their registered SSOT rather than copied into this pointer.
