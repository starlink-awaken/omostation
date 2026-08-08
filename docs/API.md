# Agora API / Usage Reference

> Quick reference for using **Agora** programmatically and from the command line.

## Command Line

- `uv run python -m agora` — run Agora entrypoints

## Programmatic API

Use `agora.mcp.resolver.resolve_bos_uri(uri)` to resolve BOS URIs.

## Configuration

- Stack: python
- Dependencies: see [`../pyproject.toml`](../pyproject.toml) (Python) or [`../package.json`](../package.json) (TypeScript).
- Environment variables and ports: see workspace `protocols/port-registry.yaml` and root `.env.example`.

## Tests

See [`../README.md`](../README.md) for the test command.
