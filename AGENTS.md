# AGENTS.md — Workspace Development Guide

> Multi-project knowledge engineering & research workspace (root directory).

## Project Overview

This root directory is a **multi-project workspace** containing independent git repos:

| Project | Stack | Location | Status |
|---------|-------|----------|--------|
| `kairon` | Python (uv, pytest) | `projects/kairon/` | Active — 17 packages |
| `SharedBrain` | Python | `projects/SharedBrain/` | Active — Digital Life OS |
| `agentmesh` | TypeScript (bun) | `projects/agentmesh/` | Active — Agent SDK |
| `gbrain` | TypeScript (bun) | `projects/gbrain/` | Active — Knowledge Brain |

**Also contains:**
- `data/db/` — Local SQLite databases (execution.db, memory.db)
- `.omo/` — Workspace governance (metadata, standards, retrospectives)
- `.hermes/` — Hermes adapter and scripts
- `SharedBrain/` — Central skill/data repository

## Essential Commands

### Root Makefile

```bash
# Run kairon tests (all 17 packages)
make kairon-test

# Ruff lint check
make kairon-lint

# Install kairon
make kairon-build
```

### Per-Project Commands

```bash
# kairon (projects/kairon/)
cd projects/kairon && make test         # All packages
cd projects/kairon && make test-fast   # Unit tests only
cd projects/kairon && make lint       # Ruff check

# gbrain (projects/gbrain/) — See AGENTS.md in that directory
cd projects/gbrain && bun test
cd projects/gbrain && bun run ci:local

# agentmesh (projects/agentmesh/) — See AGENTS.md there
cd projects/agentmesh && bun install
```

## Architecture

### Two-Layer Structure

1. **Projects layer** (`projects/`) — Independent git repos, each with own build/test/lint commands
2. **Governance layer** (`.omo/`) — Workspace metadata, standards, retrospective docs

### Data Flow

```
Agent Input → SharedBrain/ (central skills + data)
            ↓
         kairon/ (processing, reasoning)
            ↓
         gbrain/ (knowledge storage)
            ↓
         agentmesh/ (execution)
```

### Key Dependencies

- **gbrain** depends on **agentmesh** (SDK)
- **kairon/agora** provides service discovery/routing
- **SharedBrain** hosts central skills referenced by gbrain

## Testing Pattern

### Integration Tests

Located at `tests/integration/` in root:

```bash
# Run all integration tests
cd tests/integration && ./run-all.sh

# Individual test scripts:
./test-01-identity.sh
./test-02-pipeline.sh
./test-03-constraints.sh
./test-04-phase-lock.sh
./test-05-pricing.sh
./test-06-trace.sh
./test-07-collab-agentmesh.sh
./test-08-knowledge-pipeline.sh
./test-09-agora-degrade.sh
./test-10-runtime-check.sh
./test-11-i0-integration.sh
```

### CI Configuration

GitHub Actions workflows in `.github/workflows/`:
- `pytest.yml` — Runs kairon package tests
- `integration.yml` — Integration test suite
- `quality.yml` — Lint and formatting
- Others for specific checks

## Gotchas

1. **kairon uses uv** — Not pip/poetry. `uv sync` to install, `uv add <package>` to add deps.

2. **Python 3.13** — kairon targets Python 3.13+ (`ruff` config shows `target-version = "py313"`)

3. **agentmesh needs bun** — Uses Bun as runtime, not Node/npm:
   ```bash
   # Install dependencies
   cd projects/agentmesh && bun install
   ```

4. **Database paths are gitignored** — `data/db/` and each project's local DB files are `.gitignore`d

5. **Cross-project dependencies** — Each repo is independent; changes to one don't automatically reflect in others

6. **No root-level test command** — Tests run per-project (via project Makefiles)

7. **SharedBrain has its own AGENTS.md** — Per-project docs may have additional requirements

## Style Conventions

### Python (kairon)

- **Formatter**: ruff (`ruff format packages/`)
- **Linter**: ruff (`ruff check packages/`)
- **Line length**: 120
- **Target**: Python 3.13+
- **Import sorting**: isort enabled via ruff

### TypeScript (gbrain, agentmesh)

- **Formatter/Auto-fix**: bun fmt / bun run lint:fix
- **Testing**: bun test + bun run ci:local

## File Organization

- `projects/*/` — Independent project repos
- `.omo/` — Workspace governance docs (read for context, don't modify without clear reason)
- `tests/integration/` — E2E test scripts
- `scripts/` — Utility scripts and automation
- `.github/workflows/` — CI configurations
- `.hermes/` — Hermes-related scripts and adapters

## Reading Before Working

- **For kairon work**: Read `projects/kairon/pyproject.toml` for package structure
- **For gbrain work**: Read `projects/gbrain/AGENTS.md` + `projects/gbrain/CLAUDE.md`
- **For governance**: Read `.omo/standards/` for architectural standards
- **For integration tests**: Read individual test scripts in `tests/integration/`