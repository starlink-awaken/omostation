---
title: TROUBLESHOOTING
type: doc
---

# kairon Troubleshooting

## Installation / Setup

- **Missing dependencies**: run the install command from [`../README.md`](../README.md) (`uv sync`, `bun install`, or `docker compose pull`).
- **Wrong Python/Node version**: check `pyproject.toml` / `package.json` requirements.

## Tests

- **Test command fails**: ensure dependencies are installed and no other process holds required ports.
- **Flaky tests**: some tests depend on external services (e.g. Ollama, network). Run with mocks or skip integration tests if documented.

## Runtime / Configuration

- **Port conflicts**: verify `protocols/port-registry.yaml` and root `.env.example`.
- **`.omo/` state issues**: use the OMO CLI/MCP instead of editing files directly.

## Getting Help

- Developer rules: [`../AGENTS.md`](../AGENTS.md)
- AI session context: [`../CLAUDE.md`](../CLAUDE.md)
- Workspace architecture: [`../../../ARCHITECTURE.md`](../../../ARCHITECTURE.md)
