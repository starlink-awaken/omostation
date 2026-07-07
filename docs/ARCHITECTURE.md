# runtime Architecture

> Architecture overview for **runtime**. For the full workspace architecture, see [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md).

## Responsibilities

runtime is part of the eCOS v6 workspace. See [`../README.md`](../README.md) for a one-line description and [`../CAPABILITY-MAP.md`](../CAPABILITY-MAP.md) for capability mapping.

## Key Surfaces

- `src/runtime/matrix.py` — service matrix
- `src/runtime/scheduler.py` — scheduler
- `src/runtime/kei.py` — KEI sandbox
- `src/runtime/cron_service/` — cron services
- `src/runtime/mcp_server.py` — MCP server

## Design Notes

- Runtime facts (counts, ports, health) are intentionally not maintained here. Use the workspace registries and project source as the truth.
- For boundaries and call chains, read [`../BOUNDARY.md`](../BOUNDARY.md) and [`../CALLCHAIN.md`](../CALLCHAIN.md).
- For developer rules, read [`../AGENTS.md`](../AGENTS.md).
