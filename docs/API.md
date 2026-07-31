# Cockpit API / Usage Reference

> Quick reference for using **Cockpit** programmatically and from the command line.

## Command Line

- `uv run python -m cockpit` — CLI
- `uv run python src/cockpit/dashboard_server.py` — dashboard

## Programmatic API

Import `cockpit.cli` or use the MCP server for programmatic access.

## Configuration

- Stack: python
- Dependencies: see [`../pyproject.toml`](../pyproject.toml) (Python) or [`../package.json`](../package.json) (TypeScript).
- Environment variables and ports: see workspace `protocols/port-registry.yaml` and root `.env.example`.

## Tests

See [`../README.md`](../README.md) for the test command.
