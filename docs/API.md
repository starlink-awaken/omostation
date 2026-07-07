# OMO API / Usage Reference

> Quick reference for using **OMO** programmatically and from the command line.

## Command Line

- `omo doctor` — health check
- `omo inspect` — completeness/references/schemas
- `omo report` — combined report
- `omo lint projection-guard` — P74 projection guard
- `omo lint stamp-policy` — P74 stamp policy

## Programmatic API

Import `omo.cli` or run `uv run python -m omo.cli <cmd>`.

## Configuration

- Stack: python
- Dependencies: see [`../pyproject.toml`](../pyproject.toml) (Python) or [`../package.json`](../package.json) (TypeScript).
- Environment variables and ports: see workspace `protocols/port-registry.yaml` and root `.env.example`.

## Tests

See [`../README.md`](../README.md) for the test command.
