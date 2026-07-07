# runtime API / Usage Reference

> Quick reference for using **runtime** programmatically and from the command line.

## Command Line

- `uv run python -m runtime` — CLI
- `make fmt` — format
- `make sync-state` — sync state

## Programmatic API

Import `runtime.matrix`, `runtime.scheduler`, or `runtime.kei`.

## Configuration

- Stack: python
- Dependencies: see [`../pyproject.toml`](../pyproject.toml) (Python) or [`../package.json`](../package.json) (TypeScript).
- Environment variables and ports: see workspace `protocols/port-registry.yaml` and root `.env.example`.

## Tests

See [`../README.md`](../README.md) for the test command.
