<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-02 | Updated: 2026-08-02 -->

# docs/

## Purpose
`docs/` is the workspace **documentation center** — the human-readable face of eCOS v6. It contains architecture documents, operational guides, governance reports, contract specifications, and machine-generated indexes. Critically, `docs/generated/` is a **machine-maintained** subtree produced by `bin/` scripts and must never be hand-edited.

## Key Files
| File | Description |
|------|-------------|
| `SYSTEM-INDEX.md` | Unified navigation hub — entry point for all workspace documentation |
| `PANORAMA.md` | System panorama — full workspace overview and BOS routing |
| `VISION-ROADMAP.md` | Strategic vision and multi-phase roadmap |
| `FUNCTIONAL-CAPABILITY-MAP.md` | Functional capability inventory across all projects |
| `ARCHITECTURE-DETAILED-MAP.md` | Deep-dive architecture map with layer/project placement |
| `I0-AGORA-CALLCHAIN.md` | Agora MCP service callchain documentation |
| `project-registry.yaml` | **SSOT**: project metadata registry (name, layer, repo, health) |
| `layer-contract.yaml` | Layer dependency contract — defines allowed cross-layer calls |
| `AGENT-ISOLATION-ROLLOUT.md` | Agent isolation rollout plan (worktree-based GaC) |
| `INDEX-PROJECTS.md` | **Generated**: project index by layer/stack |
| `INDEX-TOOLS.md` | **Generated**: tools and scripts index |
| `INDEX-KNOWLEDGE.md` | **Generated**: knowledge/ADR/pattern index |
| `INDEX-AGENTS.md` | **Generated**: agent skills and setup index |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `generated/` | **MACHINE-GENERATED** — indexes, reports, redlines. Do NOT hand-edit. |
| `architecture/` | Architecture deep-dive documents |
| `closeout/` | Closeout reports and retrospectives |
| `contracts/` | Contract specifications (internal/external) |
| `isa/` | ISA (Ideal State Artifact) documents |
| `local-compute/` | Local compute architecture docs |
| `operations/` | Operational runbooks, SOPs, guides |
| `overview/` | High-level overview documents |
| `proposals/` | Design proposals and RFCs |
| `reports/` | Generated and manual reports |

## For AI Agents

### Working In This Directory
- **CRITICAL**: `docs/generated/` files are auto-produced by `bin/` scripts. Never hand-edit them. Regenerate via make targets.
- `project-registry.yaml` is the SSOT for project metadata. Update it when adding/removing projects.
- `layer-contract.yaml` defines the layer dependency contract. Changes require ADR approval.
- Manual docs (architecture/, operations/, proposals/) are free to edit with proper context.

### Testing Requirements
```bash
# SSOT lint — ensures docs don't hard-code runtime facts
uv run --with "pyyaml" python "bin/ssot/doc-ssot-lint.py" --json

# Doc governance check
uv run --with "pyyaml" python "bin/ssot/doc-governance-check.py"
```

### Common Patterns
- Generated files have a header comment: `<!-- GENERATED ... -->` or `# Generated:`.
- Manual docs use the `<!-- Parent: -->` comment to indicate hierarchy.
- Index files follow the pattern: `INDEX-<CATEGORY>.md`.

## Dependencies

### Internal
- `bin/ssot/` — generators that produce docs/generated/ content
- `bin/gac/gac-local-gate.py` — validates doc changes against governance rules
- `.omo/state/system.yaml` — runtime state consumed by generators
- `.omo/_truth/registry/agent-workflows.yaml` — workflow metadata for INDEX-AGENTS.md

### External
- No external package dependencies for documentation itself
- Generators use `pyyaml`, `jinja2` (for templates)

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
