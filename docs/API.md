# ecos API / Usage Reference

> Quick reference for using **ecos** programmatically and from the command line.

## Command Line

- `uv run python -m ecos` — ecos CLI
- `src/ecos/ssot/tools/mof-schema-validate.py` — MOF schema validate

## Programmatic API

Import `ecos.ssot.tools` for MOF model operations.

## Configuration

- Stack: python
- Dependencies: see [`../pyproject.toml`](../pyproject.toml) (Python) or [`../package.json`](../package.json) (TypeScript).
- Environment variables and ports: see workspace `protocols/port-registry.yaml` and root `.env.example`.

## Tests

See [`../README.md`](../README.md) for the test command.
