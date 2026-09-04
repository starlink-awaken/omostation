---
title: API
type: doc
---

# kairon API / Usage Reference

> Quick reference for using **kairon** programmatically and from the command line.

## Command Line

- `make test-diff` — changed-surface tests
- `make lint` — lint
- `make test` — full test

## Programmatic API

Import package modules directly, e.g. `import kairon_...` or use per-package APIs.

## Configuration

- Stack: python
- Dependencies: see [`../pyproject.toml`](../pyproject.toml) (Python) or [`../package.json`](../pyproject.toml) (TypeScript).
- Environment variables and ports: see workspace `protocols/port-registry.yaml` and root `.env.example`.

## Tests

See [`../README.md`](../README.md) for the test command.
